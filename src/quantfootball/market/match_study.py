"""Freeze actual model/market comparisons before kickoff, without ticket ROI."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from quantfootball.data.results import ResultLookup
from quantfootball.data.sporting_status import SportingStatusLookup
from quantfootball.market.prospective import scores
from quantfootball.market.snapshots import instant, key

NAMES = ("forecast.json", "snapshot.json", "config.json")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def validate(report, now):
    if (report.get("is_example") or report["comparison"].get("is_example")
            or report["scope"] != "sporting_match_probabilities_only"):
        raise ValueError("Only actual match probability studies are allowed.")
    created, decision = instant(report["created_at"]), instant(report["comparison"]["decision_at"])
    if not instant(report["snapshot_at"]) <= decision <= created <= now:
        raise ValueError("Invalid source, decision or prediction chronology.")
    if (not report["comparison"]["available_to_this_app_before_decision"]
        or instant(report["comparison"]["retrieved_at"]) > decision):
        raise ValueError("The comparison was not available at the decision time.")
    if datetime.fromisoformat(report["model"]["training_last_date"]).date() >= datetime.fromisoformat(report["cutoff"]).date():
        raise ValueError("Training history reaches the forecast cutoff.")
    if datetime.fromisoformat(report["cutoff"]).date() > created.astimezone(ZoneInfo("Europe/Madrid")).date():
        raise ValueError("Training cutoff is in the future.")
    forecasts = {f["position"]: f for f in report["fixtures"]}
    if len(forecasts) != len(report["fixtures"]):
        raise ValueError("Repeated fixture position.")
    identities = set()
    for f in report["fixtures"]:
        identity = (*key(f), f["date"][:10])
        if identity in identities or now >= instant(f["starts_at"]):
            raise ValueError("Repeated or already-started fixture.")
        identities.add(identity)
    compared = set()
    for f in report["comparison"]["fixtures"]:
        forecast = forecasts[f["position"]]
        if f["position"] in compared or key(f) != key(forecast) or f["date"] != forecast["date"][:10]:
            raise ValueError("Repeated or mismatched market fixture.")
        compared.add(f["position"])
        if not np.allclose(f["model_1x2"], [forecast[p] for p in ("p_home", "p_draw", "p_away")], atol=1e-12, rtol=0):
            raise ValueError("The comparison uses different model predictions.")
        if instant(f["starts_at"]) != instant(forecast["starts_at"]) or instant(f["latest_quote_at"]) > instant(report["snapshot_at"]):
            raise ValueError("Invalid market kickoff or source timestamp.")
        for name in ("model_1x2", "market_1x2"):
            p = np.asarray(f[name], dtype=float)
            if p.shape != (3,) or not np.isfinite(p).all() or (p <= 0).any() or not np.isclose(p.sum(), 1):
                raise ValueError("Invalid three-way probabilities.")
    if not compared or len(compared) != report["comparison"]["matched_fixtures"]:
        raise ValueError("A nonempty consistent comparison is required.")


def seal_study(folder):
    folder = Path(folder)
    report = read(folder / "forecast.json")
    now = datetime.now(UTC)
    validate(report, now)
    if digest(folder / "config.json") != report["inputs_sha256"]["config"] or read(folder / "config.json") != report["config"]:
        raise ValueError("Frozen configuration differs from the forecast.")
    if digest(folder / "snapshot.json") != report["inputs_sha256"]["snapshot"]:
        raise ValueError("Frozen odds differ from the forecast inputs.")
    seal = {"schema_version": 1, "registered_at": now.isoformat(), "scope": report["scope"],
        "paper_only": True, "full_ticket_roi_eligible": False,
        "primary_metric": "paired model minus market mean log loss, per competition",
        "secondary_metrics": ["multiclass_brier", "accuracy"],
        "selection_policy": report.get("selection_policy", "All correctly identified eligible upcoming fixtures in the initial capture; no post-result selection"),
        "deduplication": "First locally registered probability for each competition/date/home/away",
        "files_sha256": {name: digest(folder / name) for name in NAMES},
        "limitations": "Local clock and fingerprints, not an externally certified timestamp or actual bet"}
    save(folder / "seal.json", seal)
    return seal


def verify_study(folder):
    folder = Path(folder)
    seal = read(folder / "seal.json")
    if set(seal["files_sha256"]) != set(NAMES) or any(digest(folder / name) != sha for name, sha in seal["files_sha256"].items()):
        raise ValueError("Market study has changed or its inventory is invalid.")
    report = read(folder / "forecast.json")
    validate(report, instant(seal["registered_at"]))
    if digest(folder / "config.json") != report["inputs_sha256"]["config"] or read(folder / "config.json") != report["config"]:
        raise ValueError("Frozen configuration is inconsistent.")
    if digest(folder / "snapshot.json") != report["inputs_sha256"]["snapshot"]:
        raise ValueError("Frozen snapshot is inconsistent.")
    return seal, report


def evaluate_studies(root, dataset, *, sporting_snapshots=None):
    data = pd.read_parquet(dataset)
    results = ResultLookup(data)
    statuses = SportingStatusLookup(sporting_snapshots)
    root, entries, ready, evaluated, seen = Path(root), [], [], [], set()
    exclusions = []
    for folder in sorted(root.iterdir()) if root.exists() else []:
        if not folder.is_dir():
            continue
        try:
            seal, report = verify_study(folder)
            ready.append((instant(seal["registered_at"]), folder.name, report))
        except (ValueError, OSError, TypeError, KeyError) as exc:
            entries.append({"record": folder.name, "status": "invalid", "reason": str(exc)})
    pending = 0
    for stamp, name, report in sorted(ready, key=lambda item: item[0]):
        completed, known_results, duplicated, excluded_count = 0, 0, 0, 0
        for fixture in report["comparison"]["fixtures"]:
            resolved = results.find(fixture, stamp)
            exclusion = statuses.find(fixture, stamp)
            if resolved and exclusion:
                raise ValueError("A fixture cannot be both completed and administratively excluded.")
            excluded_count += int(exclusion is not None)
            identity = (*key(fixture), resolved["actual_date"] if resolved else fixture["date"])
            target = resolved["target"] if resolved else None
            known_results += int(target is not None)
            if identity in seen:
                duplicated += 1
                continue
            seen.add(identity)
            if exclusion:
                exclusions.append({"record": name, "position": fixture["position"], **exclusion})
                continue
            if target is None:
                pending += 1
                continue
            completed += 1
            evaluated.append({"record": name, "registered_at": stamp.isoformat(),
                **{k: fixture[k] for k in ("competition_code", "date", "home_team", "away_team")},
                "actual_date": resolved["actual_date"], "result_match_method": resolved["result_match_method"],
                "model": scores(np.asarray(fixture["model_1x2"]), target),
                "market": scores(np.asarray(fixture["market_1x2"]), target)})
        status = ("pending_results" if known_results + excluded_count < len(report["comparison"]["fixtures"])
                  else "completed_with_sporting_exclusions" if excluded_count else "completed")
        entries.append({"record": name, "status": status,
                        "scored_unique_fixtures": completed, "coverage": report["comparison"]["matched_fixtures"],
                        "known_result_fixtures": known_results, "deduplicated_fixtures": duplicated,
                        "sporting_excluded_fixtures": excluded_count,
                        "missing_market": report["comparison"]["missing"]})
    leagues = {}
    for code in sorted({r["competition_code"] for r in evaluated}):
        group = [r for r in evaluated if r["competition_code"] == code]
        leagues[code] = {"paired_matches": len(group),
            **{name: {metric: float(np.mean([r[name][metric] for r in group]))
                       for metric in ("log_loss", "brier", "accuracy")} for name in ("model", "market")},
            "model_minus_market_log_loss": float(np.mean([r["model"]["log_loss"] - r["market"]["log_loss"] for r in group]))}
    return {"created_at": datetime.now(UTC).isoformat(), "records": entries,
        "completed_unique_fixtures": len(evaluated), "pending_unique_fixtures": pending,
        "sporting_excluded_unique_fixtures": len(exclusions), "sporting_exclusions": exclusions,
        "leagues": leagues, "fixtures": evaluated, "dataset_sha256": digest(dataset),
        "roi": None, "positive_expected_roi_demonstrated": False,
        "limitations": ["No ticket, Pleno or ROI evaluation", "Exact paired match subset only",
                        "No model tuning or significance claim on this accumulating sample",
                        "Sporting scores and administratively awarded Quiniela signs may differ",
                        "Small date changes use a unique same-competition, same-team result within three days and are audited"]}
