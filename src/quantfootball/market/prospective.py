"""Pre-kickoff paired probability records, separate from full-ticket ROI records."""

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from quantfootball.data.results import ResultLookup
from quantfootball.data.sporting_status import SportingStatusLookup
from quantfootball.market.snapshots import instant, key, source_url
from quantfootball.quiniela.dashboard import render_dashboard

ROOT = Path(__file__).resolve().parents[3]
FILES = {"candidate.json", "comparator.json", "observation.json", "protocol.json",
         "candidate_config.json", "comparator_config.json"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def probabilities(fixture):
    values = np.asarray([fixture[p] for p in ("p_home", "p_draw", "p_away")], dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any() or not np.isclose(values.sum(), 1):
        raise ValueError("Invalid probabilities.")
    return values


def validate_pair(candidate, comparator, observation, protocol, now, *, frozen_config_folder=None):
    source_url(observation["source_url"])
    if observation.get("official_order_verified") is False:
        raise ValueError("Provisional coupon order must be confirmed before official probability registration.")
    deadline = instant(observation["closes_at"])
    if observation.get("is_example") or not instant(observation["captured_at"]) <= now < deadline:
        raise ValueError("Real official observation before the deadline is required.")
    if len(observation["fixtures"]) != 15 or [f["position"] for f in observation["fixtures"]] != list(range(1, 16)):
        raise ValueError("Identify all fifteen official positions, including unsupported ones.")
    candidate_coupon = candidate["coupons"][0]
    if instant(protocol["created_at"]) > min(instant(report["created_at"]) for report in (candidate, comparator)):
        raise ValueError("The protocol must precede both forecasts.")
    history_inputs = []
    for name, report in (("candidate", candidate), ("comparator", comparator)):
        if report.get("is_example") or len(report["coupons"]) != 1 or instant(report["created_at"]) > now:
            raise ValueError("One actual forecast created before registration is required.")
        expected_config = (Path(frozen_config_folder) / f"{name}_config.json"
                           if frozen_config_folder else ROOT / protocol[f"{name}_config"])
        expected_hash = protocol[f"{name}_config_sha256"]
        if (digest(expected_config) != expected_hash or report["config"] != read(expected_config)
                or expected_hash not in report["inputs"].values()):
            raise ValueError("Configuration differs from the previously frozen protocol.")
        # Changes to collection/UI code are allowed; the prediction models stay frozen.
        prediction_files = {p.replace("\\", "/") for p in protocol.get(f"{name}_prediction_files", [])}
        for path, sha in protocol["source_sha256"].items():
            required = path.replace("\\", "/").startswith("src/quantfootball/models/") or path.replace("\\", "/") in prediction_files
            if required and report["source_sha256"].get(path) != sha:
                raise ValueError("Prediction code differs from the frozen model protocol.")
        coupon = report["coupons"][0]
        history_inputs.append(sorted((Path(p).name, sha) for p, sha in report["inputs"].items()
                                     if Path(p).suffix == ".parquet"))
        cutoff = datetime.fromisoformat(coupon["cutoff"]).date()
        if (cutoff > instant(report["created_at"]).astimezone(ZoneInfo("Europe/Madrid")).date()
                or datetime.fromisoformat(coupon["model"]["training_last_date"]).date() >= cutoff):
            raise ValueError("Training reaches the forecast cutoff or uses a future cutoff.")
        if len(coupon["fixtures"]) != 14 or [f["position"] for f in coupon["fixtures"]] != list(range(1, 15)):
            raise ValueError("Fourteen ordered forecasts are required.")
        if (coupon["cutoff"] != candidate_coupon["cutoff"]
                or coupon["model"]["training_last_date"] != candidate_coupon["model"]["training_last_date"]):
            raise ValueError("Paired models require the same training cutoff.")
        if not protocol["evaluation_start_inclusive"] <= observation["fixtures"][0]["date"] < protocol["evaluation_end_exclusive"]:
            raise ValueError("Contest is outside the frozen evaluation period.")
        for forecast, official in zip(coupon["fixtures"], observation["fixtures"][:14]):
            kickoff = instant(official["starts_at"])
            if (key(forecast) != key(official) or now >= kickoff or deadline > kickoff
                or forecast["date"][:10] != kickoff.astimezone(ZoneInfo("Europe/Madrid")).date().isoformat()):
                raise ValueError("Forecast and official schedule differ or a match has started.")
            probabilities(forecast)
    if len({key(f) for f in candidate_coupon["fixtures"]}) != 14:
        raise ValueError("Repeated forecast fixture.")
    if not history_inputs[0] or history_inputs[0] != history_inputs[1]:
        raise ValueError("Paired models must use the same frozen historical dataset.")


def register_pair(candidate_path, comparator_path, observation_path, protocol_path, root):
    values = [read(p) for p in (candidate_path, comparator_path, observation_path, protocol_path)]
    candidate, _comparator, observation, protocol = values
    now = datetime.now(UTC)
    validate_pair(*values, now)
    identifier = observation["contest_id"]
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", identifier):
        raise ValueError("Invalid contest identifier.")
    folder = Path(root) / identifier
    folder.mkdir(parents=True, exist_ok=False)
    for name, value in zip(("candidate.json", "comparator.json", "observation.json", "protocol.json"), values):
        save(folder / name, value)
    for name in ("candidate", "comparator"):
        with (folder / f"{name}_config.json").open("xb") as handle:
            handle.write((ROOT / protocol[f"{name}_config"]).read_bytes())
    now = datetime.now(UTC)
    validate_pair(*values, now)
    seal = {"schema_version": 1, "registered_at": now.isoformat(), "contest_id": identifier,
        "scope": "First 14 sporting match probabilities only; separate from full-ticket ROI protocol",
        "paper_only": True, "full_ticket_roi_eligible": False,
        "full_ticket_exclusion_reason": observation.get("full_ticket_exclusion_reason", "Not a full-ticket registration"),
        "primary_comparison": "candidate minus comparator mean log loss, per competition",
        "market_policy": "First eligible real market attachment before official close and all kickoffs; no later replacement",
        "deduplication": "Use the first registered match prediction for model metrics; first eligible market comparison for paired market metrics",
        "files_sha256": {name: digest(folder / name) for name in sorted(FILES)},
        "limitations": "Local clock and hashes; no external trusted timestamp and no actual bet"}
    save(folder / "seal.json", seal)
    display = {**candidate, "registration_status": "probabilities_only_before_deadline"}
    render_dashboard(display, {}, {}, folder / "dashboard.html")
    return seal


def verify_pair(folder):
    folder = Path(folder)
    seal = read(folder / "seal.json")
    if set(seal["files_sha256"]) != FILES or any(digest(folder / name) != sha for name, sha in seal["files_sha256"].items()):
        raise ValueError("Probability record has changed or has an invalid inventory.")
    values = [read(folder / name) for name in ("candidate.json", "comparator.json", "observation.json", "protocol.json")]
    validate_pair(*values, instant(seal["registered_at"]), frozen_config_folder=folder)
    return seal, values


def validate_market(comparison, candidate, observation, now):
    boundary = instant(comparison["decision_at"])
    if (comparison.get("is_example") or not comparison.get("available_to_this_app_before_decision")
        or instant(comparison["retrieved_at"]) > boundary or boundary > now
        or instant(candidate["created_at"]) > boundary
        or instant(comparison["snapshot_at"]) > instant(comparison["retrieved_at"])
        or now >= instant(observation["closes_at"])):
        raise ValueError("Only actual market data available before the declared decision and official close can be attached.")
    source_url(comparison["source_url"])
    fixtures = {f["position"]: f for f in candidate["coupons"][0]["fixtures"]}
    matched = set()
    for row in comparison["fixtures"]:
        fixture = fixtures[row["position"]]
        expected = observation["fixtures"][row["position"] - 1]
        if row["position"] in matched or now >= instant(expected["starts_at"]):
            raise ValueError("Repeated or already-started market fixture.")
        matched.add(row["position"])
        if key(fixture) != key(row) or fixture["date"][:10] != row["date"]:
            raise ValueError("Market comparison differs from the frozen fixture.")
        if (instant(row["starts_at"]) != instant(expected["starts_at"])
                or instant(row["latest_quote_at"]) > instant(comparison["snapshot_at"])):
            raise ValueError("Market kickoff or quote timing differs from the frozen record.")
        if not np.allclose(probabilities(fixture), row["model_1x2"], atol=1e-12, rtol=0):
            raise ValueError("Market comparison uses different model predictions.")
        values = np.asarray(row["market_1x2"], dtype=float)
        if values.shape != (3,) or not np.isfinite(values).all() or (values <= 0).any() or not np.isclose(values.sum(), 1):
            raise ValueError("Invalid market probabilities.")
    if not matched or len(matched) != comparison["matched_fixtures"]:
        raise ValueError("A nonempty consistent market comparison is required.")


def attach_market(folder, comparison_path):
    folder = Path(folder)
    seal, values = verify_pair(folder)
    candidate, _, observation, _ = values
    comparison = read(comparison_path)
    now = datetime.now(UTC)
    validate_market(comparison, candidate, observation, now)
    if (folder / "market.json").exists() or (folder / "market_seal.json").exists():
        raise ValueError("The first market attachment already exists; it cannot be replaced.")
    save(folder / "market.json", comparison)
    now = datetime.now(UTC)
    validate_market(comparison, candidate, observation, now)
    market_seal = {"attached_at": now.isoformat(), "model_seal_sha256": digest(folder / "seal.json"),
                   "market_sha256": digest(folder / "market.json"), "contest_id": seal["contest_id"]}
    save(folder / "market_seal.json", market_seal)
    return market_seal


def scores(p, target):
    return {"log_loss": float(-np.log(p[target])),
            "brier": float(np.square(p - np.eye(3)[target]).sum()),
            "accuracy": float(np.argmax(p) == target)}


def evaluate_pairs(root, dataset_path, *, sporting_snapshots=None):
    data = pd.read_parquet(dataset_path)
    data["date"] = pd.to_datetime(data["date"])
    results = ResultLookup(data)
    statuses = SportingStatusLookup(sporting_snapshots)
    records, prepared, rows, seen, market_seen = [], [], [], set(), set()
    root = Path(root)
    for folder in sorted(root.iterdir()) if root.exists() else []:
        if not folder.is_dir():
            continue
        try:
            seal, values = verify_pair(folder)
            comparison = None
            if (folder / "market.json").exists() or (folder / "market_seal.json").exists():
                attachment, comparison = read(folder / "market_seal.json"), read(folder / "market.json")
                if (attachment["model_seal_sha256"] != digest(folder / "seal.json")
                    or attachment["market_sha256"] != digest(folder / "market.json")):
                    raise ValueError("Market attachment has changed.")
                validate_market(comparison, values[0], values[2], instant(attachment["attached_at"]))
            prepared.append((instant(seal["registered_at"]), folder.name, values, comparison))
        except (ValueError, KeyError, OSError, TypeError, IndexError) as exc:
            records.append({"record": folder.name, "status": "invalid", "reason": str(exc)})
    pending, exclusions = 0, []
    for stamp, name, values, comparison in sorted(prepared, key=lambda item: item[0]):
        candidate, comparator, _, _ = values
        markets = {f["position"]: f for f in comparison["fixtures"]} if comparison else {}
        complete, excluded_count = 0, 0
        for c, b in zip(candidate["coupons"][0]["fixtures"], comparator["coupons"][0]["fixtures"]):
            resolved = results.find(c, stamp)
            exclusion = statuses.find(c, stamp)
            if resolved and exclusion:
                raise ValueError("A fixture cannot be both completed and administratively excluded.")
            fixture_key = (*key(c), resolved["actual_date"] if resolved else c["date"][:10])
            target = resolved["target"] if resolved else None
            is_new = fixture_key not in seen
            seen.add(fixture_key)
            if target is None:
                if exclusion:
                    excluded_count += 1
                    if is_new:
                        exclusions.append({"record": name, "position": c["position"], **exclusion})
                else:
                    pending += int(is_new)
                continue
            complete += 1
            row = {"record": name, "registered_at": stamp.isoformat(), "competition_code": c["competition_code"],
                   "date": c["date"][:10], "actual_date": resolved["actual_date"],
                   "result_match_method": resolved["result_match_method"],
                   "home_team": c["home_team"], "away_team": c["away_team"],
                   "target_index_1x2": target, "use_for_model_metrics": is_new,
                   "candidate": scores(probabilities(c), target), "comparator": scores(probabilities(b), target)}
            if c["position"] in markets and fixture_key not in market_seen:
                market_seen.add(fixture_key)
                row["market"] = scores(np.asarray(markets[c["position"]]["market_1x2"]), target)
            rows.append(row)
        status = ("complete" if complete == 14 else "complete_with_sporting_exclusions"
                  if complete + excluded_count == 14 else "pending_results")
        records.append({"record": name, "status": status, "completed_fixtures": complete,
                        "sporting_excluded_fixtures": excluded_count, "market_matches": len(markets)})
    by_code = {}
    for code in sorted({r["competition_code"] for r in rows}):
        selected = [r for r in rows if r["competition_code"] == code and r["use_for_model_metrics"]]
        matched = [r for r in rows if r["competition_code"] == code and "market" in r]
        def average(group, model):
            return {metric: float(np.mean([r[model][metric] for r in group]))
                    for metric in ("log_loss", "brier", "accuracy")} if group else None
        by_code[code] = {"matches": len(selected), "candidate": average(selected, "candidate"),
            "comparator": average(selected, "comparator"), "market_matched_matches": len(matched),
            "candidate_on_market_matches": average(matched, "candidate"),
            "market_on_same_matches": average(matched, "market"),
            "candidate_minus_comparator_log_loss": float(np.mean([r["candidate"]["log_loss"] - r["comparator"]["log_loss"] for r in selected])) if selected else None,
            "candidate_minus_market_log_loss": float(np.mean([r["candidate"]["log_loss"] - r["market"]["log_loss"] for r in matched])) if matched else None}
    return {"created_at": datetime.now(UTC).isoformat(), "records": records, "pending_unique_fixtures": pending,
        "sporting_excluded_unique_fixtures": len(exclusions), "sporting_exclusions": exclusions,
        "completed_unique_fixtures": sum(r["use_for_model_metrics"] for r in rows), "leagues": by_code,
        "fixtures": rows, "dataset_sha256": digest(dataset_path), "paper_only": True,
        "roi": None, "positive_expected_roi_demonstrated": False,
        "limitations": ["Sporting results only; awarded Quiniela signs may differ",
                        "This probability study cannot calculate full-ticket ROI or Pleno performance",
                        "Missing market fixtures remain missing; evaluate the exact paired subset",
                        "No significance claim or model tuning on this accumulating cohort",
                        "Small date changes use a unique same-competition, same-team result within three days and are audited"]}
