"""Versioned paper decisions, including abstentions, with immutable input snapshots.

Economic deployment is deliberately unavailable until a separately reviewed prize
model and prospective protocol exist. Hypothetical sensitivity never enables play.
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from quantfootball.market.snapshots import instant, key, source_url
from quantfootball.quiniela.coverage import validate_probabilities
from quantfootball.quiniela.payout_scenarios import cents
from quantfootball.quiniela.registry import digest, write_new

SCOPE = {"es.1": "men", "es.2": "men", "es.w.1": "women"}
ECONOMIC_BLOCKERS = ["joint_crowd_model_not_validated", "prize_model_not_validated",
                     "economic_prospective_protocol_not_registered"]


def observation_identity(fixture):
    if fixture["competition_code"] in SCOPE:
        return key(fixture)
    # Out-of-scope contests still deserve an abstention record. No prediction
    # lookup is attempted for their unaudited team names.
    values = tuple(str(fixture[k]).strip() for k in ("competition_code", "home_team", "away_team"))
    if not all(values) or values[1] == values[2]:
        raise ValueError("Invalid out-of-scope fixture identity.")
    return values


def validate_observation(observation, now):
    if observation.get("is_example") or observation.get("official_order_verified") is not True:
        raise ValueError("A verified actual official coupon is required for a prospective decision.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", observation["contest_id"]):
        raise ValueError("Unsafe contest identifier.")
    source_url(observation["source_url"])
    close = instant(observation["closes_at"])
    if not instant(observation["captured_at"]) <= now < close:
        raise ValueError("Cannot backdate a decision or register a closed coupon.")
    fixtures = observation["fixtures"]
    if len(fixtures) != 15 or [f["position"] for f in fixtures] != list(range(1, 16)):
        raise ValueError("Fifteen official ordered fixtures are required.")
    identities = [observation_identity(f) for f in fixtures]
    if len(set(identities)) != 15:
        raise ValueError("Duplicate fixture identity.")
    teams = [(f.get("gender"), team) for f, identity in zip(fixtures, identities) for team in identity[1:]]
    if len(set(teams)) != 30:
        raise ValueError("The coupon repeats a team.")
    if any(close > instant(f["starts_at"]) or now >= instant(f["starts_at"]) for f in fixtures):
        raise ValueError("Decision and close must precede every kickoff.")


def prepare_decision(observation, *, maximum_budget_eur=10, forecast=None, now=None):
    now = now or datetime.now(UTC)
    validate_observation(observation, now)
    cap = cents(maximum_budget_eur)
    if not 150 <= cap <= 1000:
        raise ValueError("Maximum budget must be within 1.50–10.00 EUR.")
    reasons = list(ECONOMIC_BLOCKERS)
    if any(SCOPE.get(f["competition_code"]) != f.get("gender") for f in observation["fixtures"]):
        reasons.insert(0, "out_of_scope_coupon")
    if forecast is None:
        reasons.insert(0, "missing_probability_forecast")
    else:
        if forecast.get("is_example") or len(forecast.get("coupons", [])) != 1:
            raise ValueError("Use one actual forecast.")
        created = instant(forecast["created_at"])
        if created > now or (now - created).total_seconds() > 48 * 3600:
            raise ValueError("Forecast is future-dated or older than 48 hours.")
        coupon = forecast["coupons"][0]
        predicted = [*coupon["fixtures"], coupon["pleno"]]
        if len(predicted) != 15 or any(key(a) != key(b) for a, b in zip(predicted, observation["fixtures"])):
            raise ValueError("Forecast identities differ from the official coupon.")
        if coupon["model"]["training_last_date"][:10] >= coupon["cutoff"][:10]:
            raise ValueError("Training reaches the decision cutoff.")
        if coupon["cutoff"][:10] > created.astimezone(ZoneInfo("Europe/Madrid")).date().isoformat():
            raise ValueError("Forecast cutoff is later than its creation.")
        if [f["position"] for f in coupon["fixtures"]] != list(range(1, 15)):
            raise ValueError("Forecast positions must be ordered.")
        validate_probabilities([[f[p] for p in ("p_home", "p_draw", "p_away")]
                                for f in coupon["fixtures"]])
        for predicted_row, official in zip(predicted, observation["fixtures"]):
            if predicted_row["date"][:10] != instant(official["starts_at"]).astimezone(ZoneInfo("Europe/Madrid")).date().isoformat():
                raise ValueError("Forecast fixture date differs from the observed schedule.")
        if not forecast.get("inputs") or not forecast.get("source_sha256"):
            raise ValueError("Forecast input/code provenance is required.")
    return {
        "schema_version": 1, "contest_id": observation["contest_id"],
        "created_at": now.isoformat(), "closes_at": observation["closes_at"],
        "action": "abstain", "reason_codes": reasons, "stake_eur": 0,
        "maximum_budget_eur": cap / 100, "columns": [], "paper_only": True,
        "model": None if forecast is None else forecast.get("config"),
        "probability_any_cash": None, "probability_recover_stake": None,
        "expected_net_eur": None, "uncertainty": "insufficient_economic_evidence",
        "hypothetical_returns_enable_play": False,
        "limitations": "Prospective abstention, not an assertion that every possible bet has negative value",
    }


def register_decision(observation_path, root, *, maximum_budget_eur=10, forecast_path=None):
    # No caller-provided timestamp: the decision is registered at wall-clock time.
    observation = json.loads(Path(observation_path).read_text(encoding="utf-8"))
    forecast = json.loads(Path(forecast_path).read_text(encoding="utf-8")) if forecast_path else None
    decision = prepare_decision(observation, maximum_budget_eur=maximum_budget_eur, forecast=forecast)
    folder = Path(root) / decision["contest_id"]
    folder.mkdir(parents=True, exist_ok=False)
    write_new(folder / "observation.json", observation)
    files = ["observation.json", "decision.json"]
    if forecast is not None:
        write_new(folder / "forecast.json", forecast)
        files.append("forecast.json")
    decision["inputs_sha256"] = {p: digest(folder / p) for p in files if p != "decision.json"}
    write_new(folder / "decision.json", decision)
    validate_observation(observation, datetime.now(UTC))
    write_new(folder / "seal.json", {
        "schema_version": 1, "registered_at": datetime.now(UTC).isoformat(),
        "files_sha256": {p: digest(folder / p) for p in files},
        "source_sha256": digest(Path(__file__)), "paper_only": True,
        "limitations": "Local clock and hashes, not an externally certified timestamp",
    })
    return decision


def verify_decision(folder):
    folder = Path(folder)
    seal = json.loads((folder / "seal.json").read_text(encoding="utf-8"))
    inventory = seal["files_sha256"]
    if set(inventory) not in ({"observation.json", "decision.json"},
                              {"observation.json", "decision.json", "forecast.json"}):
        raise ValueError("Invalid decision inventory.")
    if any(digest(folder / p) != sha for p, sha in inventory.items()):
        raise ValueError("A frozen decision input has changed.")
    read = lambda p: json.loads((folder / p).read_text(encoding="utf-8"))
    decision, observation = read("decision.json"), read("observation.json")
    registered = instant(seal["registered_at"])
    validate_observation(observation, registered)
    if instant(decision["created_at"]) > registered:
        raise ValueError("Decision was created after registration.")
    recomputed = prepare_decision(observation, maximum_budget_eur=decision["maximum_budget_eur"],
                                  forecast=read("forecast.json") if "forecast.json" in inventory else None,
                                  now=instant(decision["created_at"]))
    if {k: v for k, v in decision.items() if k != "inputs_sha256"} != recomputed:
        raise ValueError("Decision differs from the frozen abstention policy.")
    if decision["inputs_sha256"] != {p: sha for p, sha in inventory.items() if p != "decision.json"}:
        raise ValueError("Decision input inventory differs.")
    return decision
