"""Local pre-deadline records and append-only settlement of paper portfolios."""

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from quantfootball.data.competitions import women_team_name
from quantfootball.data.teams import canonicalize_team
from quantfootball.market.snapshots import instant, key, source_url
from quantfootball.quiniela.dashboard import render_dashboard
from quantfootball.quiniela.settlement import (
    SELAE_ALIASES,
    parse_official_extract,
    settle_columns,
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def validate_registration(report, manifest, now):
    now = instant(now.isoformat())
    if manifest.get("official_order_verified") is False:
        raise ValueError("Confirm the provisional coupon against the official order before full-ticket registration.")
    if report.get("is_example"):
        raise ValueError("Example forecasts cannot be registered as real contests.")
    if manifest["schema_version"] not in (1, 2):
        raise ValueError("Unsupported contest manifest.")
    if manifest["schema_version"] == 2 and manifest.get("official_order_verified") is not True:
        raise ValueError("New v2 manifests require explicitly verified official order.")
    if manifest.get("is_example"):
        raise ValueError("Example manifests cannot be registered as real contests.")
    identifier = manifest["contest_id"]
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", identifier):
        raise ValueError("Use a safe unique contest identifier.")
    source_url(manifest["source_url"])
    deadline = instant(manifest["closes_at"])
    if not instant(manifest["captured_at"]) <= now < deadline:
        raise ValueError("Manifest is from the future or contest is already closed.")
    if not instant(report["created_at"]) <= now or len(report["coupons"]) != 1:
        raise ValueError("One forecast created before registration is required.")
    if not report.get("inputs") or not report.get("source_sha256"):
        raise ValueError("Forecast must include input and code fingerprints.")
    coupon = report["coupons"][0]
    fixtures = manifest["fixtures"]
    if len(fixtures) != 15 or [f["position"] for f in fixtures] != list(range(1, 16)):
        raise ValueError("Official manifest must contain ordered positions 1 through 15.")
    if len(coupon["fixtures"]) != 14 or not coupon.get("pleno"):
        raise ValueError("Fourteen forecasts and the Pleno are required.")
    if [f["position"] for f in coupon["fixtures"]] != list(range(1, 15)):
        raise ValueError("Forecast positions must be ordered 1 through 14.")
    if (
        len(
            {
                (
                    women_team_name(f[t])
                    if f["competition_code"] == "es.w.1"
                    else canonicalize_team(f[t])
                )
                for f in fixtures
                for t in ("home_team", "away_team")
            }
        )
        != 30
    ):
        raise ValueError("Contest repeats a team.")
    cutoff = datetime.fromisoformat(coupon["cutoff"]).date()
    if cutoff > now.astimezone(ZoneInfo("Europe/Madrid")).date():
        raise ValueError("Forecast cutoff is in the future.")
    if cutoff > instant(report["created_at"]).astimezone(ZoneInfo("Europe/Madrid")).date():
        raise ValueError("Training cutoff is later than forecast creation.")
    if datetime.fromisoformat(coupon["model"]["training_last_date"]).date() >= cutoff:
        raise ValueError("Training data reach the forecast cutoff.")
    forecasts = [*coupon["fixtures"], coupon["pleno"]]
    for expected, forecast in zip(fixtures, forecasts):
        kickoff = instant(expected["starts_at"])
        if not now < kickoff or deadline > kickoff:
            raise ValueError("Registration/deadline must precede all kickoffs.")
        # The Pleno originally stores no division, so validate it against its manifest.
        predicted = {
            **forecast,
            "competition_code": forecast.get("competition_code", expected["competition_code"]),
        }
        if key(predicted) != key(expected):
            raise ValueError("Forecast and official manifest have different teams/order/divisions.")
        if (
            forecast["date"][:10]
            != kickoff.astimezone(ZoneInfo("Europe/Madrid")).date().isoformat()
        ):
            raise ValueError("Forecast and official manifest have different fixture dates.")
    if len(coupon["budgets"]) != 1:
        raise ValueError("Freeze one budget, rather than choosing a budget after results.")
    pack = next(iter(coupon["budgets"].values()))
    budget = Decimal(str(pack["budget_eur"]))
    cap = Decimal("5.00") if manifest["schema_version"] == 1 else Decimal(str(manifest["maximum_budget_eur"]))
    if not cap.is_finite() or not Decimal("1.50") <= cap <= Decimal("10.00"):
        raise ValueError("Maximum budget must be finite and within 1.50–10.00 EUR.")
    if not budget.is_finite() or not Decimal("1.50") <= budget <= cap:
        raise ValueError("Budget exceeds the manifest limit (legacy v1: 5 EUR).")
    strategies = pack["strategies"]
    if manifest["primary_strategy"] not in strategies:
        raise ValueError("Predeclare the primary strategy.")
    for strategy in strategies.values():
        columns = [tuple(c["signs"]) for c in strategy["columns"]]
        if (
            not columns
            or len(set(columns)) != len(columns)
            or any(len(c) != 14 or any(s not in ("1", "X", "2") for s in c) for c in columns)
        ):
            raise ValueError("Invalid or duplicate betting columns.")
        cost = Decimal(".75") * len(columns)
        if cost > budget or Decimal(str(strategy["cost_eur"])) != cost:
            raise ValueError("Column cost does not match the frozen budget.")
    comparison = coupon.get("market_comparison")
    if comparison and comparison.get("is_example"):
        raise ValueError("Example market data cannot enter the prospective record.")
    if comparison and (
        instant(comparison["decision_at"]) > now
        or instant(comparison["retrieved_at"]) > instant(comparison["decision_at"])
        or not comparison.get("available_to_this_app_before_decision")
    ):
        raise ValueError("Market comparison was unavailable at its declared decision time.")
    return identifier


def register_forecast(forecast_path, manifest_path, root):
    # Capture actual wall-clock time here. The CLI offers no backdating argument.
    now = datetime.now(UTC)
    report = json.loads(Path(forecast_path).read_text(encoding="utf-8"))
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    identifier = validate_registration(report, manifest, now)
    folder = Path(root) / identifier
    folder.mkdir(parents=True, exist_ok=False)
    report["prospective"] = True
    report["registration_status"] = "registered_before_deadline"
    write_new(folder / "forecast.json", report)
    write_new(folder / "manifest.json", manifest)
    now = datetime.now(UTC)
    validate_registration(report, manifest, now)
    seal = {
        "schema_version": 1,
        "contest_id": identifier,
        "registered_at": now.isoformat(),
        "primary_strategy": manifest["primary_strategy"],
        "closes_at": manifest["closes_at"],
        "paper_only": True,
        "official_inputs_independently_verified": False,
        "original_forecast_sha256": digest(forecast_path),
        "files_sha256": {p: digest(folder / p) for p in ("forecast.json", "manifest.json")},
        "limitations": "Local hashes detect changes against this seal; not an external trusted timestamp or proof of a real placed bet",
    }
    write_new(folder / "seal.json", seal)
    render_dashboard(report, {}, {}, folder / "dashboard.html")
    return seal


def verify_record(folder):
    folder = Path(folder)
    seal = json.loads((folder / "seal.json").read_text(encoding="utf-8"))
    if set(seal["files_sha256"]) != {"forecast.json", "manifest.json"}:
        raise ValueError("Invalid seal file inventory.")
    for name, expected in seal["files_sha256"].items():
        if digest(folder / name) != expected:
            raise ValueError(f"Registered file changed: {name}")
    return seal


def settle_record(folder, extract_path, official_url):
    folder = Path(folder)
    seal = verify_record(folder)
    source_url(official_url)
    now = datetime.now(UTC)
    if now <= instant(seal["closes_at"]):
        raise ValueError("Contest has not closed.")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((folder / "forecast.json").read_text(encoding="utf-8"))
    coupon = report["coupons"][0]
    raw = Path(extract_path).read_text(encoding="utf-8")
    official = parse_official_extract(raw, manifest["contest_date"])
    for expected, actual in zip(manifest["fixtures"], [*official["fixtures"], official["pleno"]]):
        for side in ("home", "away"):
            if expected["competition_code"] == "es.w.1":
                if women_team_name(actual[f"{side}_raw"]) != women_team_name(
                    expected[f"{side}_team"]
                ):
                    raise ValueError("Official women's teams/order differ from frozen contest.")
                continue
            name = canonicalize_team(
                SELAE_ALIASES.get(actual[f"{side}_raw"], actual[f"{side}_raw"])
            )
            if name != canonicalize_team(expected[f"{side}_team"]):
                raise ValueError("Official settlement teams/order differ from frozen contest.")
    # Use the official awarded signs directly, including administrative results;
    # never replace them with a later sporting result from the training dataset.
    pack = next(iter(coupon["budgets"].values()))
    result = {
        "contest_id": seal["contest_id"],
        "settled_at": now.isoformat(),
        "official_url": official_url,
        "official_extract_sha256": digest(extract_path),
        "seal_sha256": digest(folder / "seal.json"),
        "primary_strategy": seal["primary_strategy"],
        "paper_only": True,
        "strategies": {},
    }
    for name, strategy in pack["strategies"].items():
        result["strategies"][name] = settle_columns(
            strategy["columns"],
            [f["sign"] for f in official["fixtures"]],
            official["prizes"],
            pleno_prediction=coupon["pleno"]["prediction"],
            pleno_actual=official["pleno"]["actual"],
        )
    # New immutable receipt, originals stay intact. An unknown winning payout fails.
    with (folder / "official_extract.txt").open("x", encoding="utf-8") as handle:
        handle.write(raw)
    result["stored_extract_sha256"] = digest(folder / "official_extract.txt")
    write_new(folder / "settlement.json", result)
    return result


def registry_summary(root):
    """List every record, including pending, corrupt and incomplete directories."""
    result = {
        "records": [],
        "settled_count": 0,
        "pending_count": 0,
        "invalid_count": 0,
        "settled_cost_eur": 0.0,
        "settled_return_eur": 0.0,
        "pending_cost_eur": 0.0,
        "paper_only": True,
        "expected_roi_demonstrated": False,
    }
    root = Path(root)
    for folder in sorted(root.iterdir()) if root.exists() else []:
        if not folder.is_dir():
            continue
        entry = {"record": folder.name}
        try:
            seal = verify_record(folder)
            report = json.loads((folder / "forecast.json").read_text(encoding="utf-8"))
            pack = next(iter(report["coupons"][0]["budgets"].values()))
            entry["primary_strategy"] = seal["primary_strategy"]
            cost = pack["strategies"][seal["primary_strategy"]]["cost_eur"]
            if (folder / "settlement.json").exists():
                receipt = json.loads((folder / "settlement.json").read_text(encoding="utf-8"))
                if (
                    receipt["seal_sha256"] != digest(folder / "seal.json")
                    or receipt["primary_strategy"] != seal["primary_strategy"]
                ):
                    raise ValueError("Settlement receipt does not match seal.")
                if receipt["stored_extract_sha256"] != digest(folder / "official_extract.txt"):
                    raise ValueError("Saved official extract has changed.")
                manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
                official = parse_official_extract(
                    (folder / "official_extract.txt").read_text(encoding="utf-8"),
                    manifest["contest_date"],
                )
                recomputed = settle_columns(
                    pack["strategies"][seal["primary_strategy"]]["columns"],
                    [f["sign"] for f in official["fixtures"]],
                    official["prizes"],
                    pleno_prediction=report["coupons"][0]["pleno"]["prediction"],
                    pleno_actual=official["pleno"]["actual"],
                )
                if receipt["strategies"][seal["primary_strategy"]] != recomputed:
                    raise ValueError("Settlement receipt differs from recomputed prizes.")
                settlement = receipt["strategies"][seal["primary_strategy"]]
                if settlement["cost_eur"] != cost:
                    raise ValueError("Settlement cost differs from registered cost.")
                entry.update(status="settled", settlement=settlement)
                result["settled_count"] += 1
                result["settled_cost_eur"] += cost
                result["settled_return_eur"] += settlement["gross_return_eur"]
            else:
                entry["status"] = "pending"
                result["pending_count"] += 1
                result["pending_cost_eur"] += cost
        except (ValueError, KeyError, OSError, TypeError, StopIteration) as exc:
            entry.update(status="invalid", reason=str(exc))
            result["invalid_count"] += 1
        result["records"].append(entry)
    result["observed_roi_settled_only"] = (
        result["settled_return_eur"] / result["settled_cost_eur"] - 1
        if result["settled_cost_eur"]
        else None
    )
    result["complete_accounting"] = not (result["pending_count"] or result["invalid_count"])
    return result
