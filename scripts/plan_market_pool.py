"""Prepare a separately versioned prospective model/market candidate before close."""

import argparse
import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from quantfootball.market.pooling import pool_probabilities
from quantfootball.market.snapshots import compare_snapshot, instant, key
from quantfootball.quiniela.dashboard import render_dashboard
from quantfootball.quiniela.uncertainty import compare_strategies

ROOT = Path(__file__).resolve().parents[1]
PROBS = ("p_home", "p_draw", "p_away")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base-forecast", "scenarios", "snapshot", "official-observation", "config", "output-dir"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    now = datetime.now(UTC)
    config, original, observation, snapshot = [read(path) for path in
        (args.config, args.base_forecast, args.official_observation, args.snapshot)]
    base_path = ROOT / config["base_config"]
    if (digest(base_path) != config["base_config_sha256"] or original["config"] != read(base_path)
            or config["base_config_sha256"] not in original["inputs"].values()):
        raise ValueError("The base forecast differs from the predeclared base configuration.")
    if (original.get("is_example") or observation.get("is_example") or snapshot.get("is_example")
            or observation.get("official_order_verified") is not True
            or len(original["coupons"]) != 1 or len(observation["fixtures"]) != 15):
        raise ValueError("One actual base forecast and fifteen user-confirmed official positions are required.")
    created = instant(original["created_at"])
    if not instant(config["predeclared_at"]) <= created <= now or now - created > timedelta(hours=48):
        raise ValueError("Use a base forecast made after this protocol and within the last 48 hours.")
    if not instant(observation["captured_at"]) <= now < instant(observation["closes_at"]):
        raise ValueError("An actual observed contest before its close is required.")
    report = copy.deepcopy(original)
    coupon = report["coupons"][0]
    if [f["position"] for f in coupon["fixtures"]] != list(range(1, 15)):
        raise ValueError("Fourteen ordered model predictions are required.")
    for forecast, official in zip([*coupon["fixtures"], coupon["pleno"]], observation["fixtures"]):
        if (key(forecast) != key(official) or now >= instant(official["starts_at"])
                or instant(observation["closes_at"]) > instant(official["starts_at"])):
            raise ValueError("Fixture identity differs or a selected fixture has started.")
    if datetime.fromisoformat(coupon["model"]["training_last_date"]).date() >= datetime.fromisoformat(coupon["cutoff"]).date():
        raise ValueError("Training reaches the forecast cutoff.")
    if args.scenarios.resolve() != (args.base_forecast.parent / "scenarios.npz").resolve():
        raise ValueError("Use the bootstrap file saved alongside this base forecast.")
    draws = np.load(args.scenarios, allow_pickle=False)["probabilities"]
    point = np.array([[row[name] for name in PROBS] for row in coupon["fixtures"]])
    if draws.ndim != 3 or draws.shape[1:] != point.shape or not 2 <= len(draws) <= 512:
        raise ValueError("Base scenarios do not match the fourteen predictions.")
    comparison = compare_snapshot(coupon, snapshot, now.isoformat())
    if not comparison["available_to_this_app_before_decision"]:
        raise ValueError("Market data were not available to the application at the declared decision time.")
    quotes = {row["position"]: row["market_1x2"] for row in comparison["fixtures"]}
    mixed, scenarios = point.copy(), draws.copy()
    applied, retained = [], []
    for i, row in enumerate(coupon["fixtures"]):
        if row["competition_code"] == "es.w.1":
            retained.append(row["position"])
            continue
        if row["position"] not in quotes:
            raise ValueError("Every men's fixture needs eligible pre-close market probabilities.")
        mixed[i] = pool_probabilities(point[i], quotes[row["position"]], market_weight=config["market_weight"])
        scenarios[:, i] = pool_probabilities(draws[:, i], quotes[row["position"]], market_weight=config["market_weight"])
        applied.append(row["position"])
    for i, row in enumerate(coupon["fixtures"]):
        for j, name in enumerate(PROBS):
            row[name] = float(mixed[i, j])
            row[name + "_low"], row[name + "_high"] = np.quantile(scenarios[:, i, j], [.05, .95]).tolist()
        row["entropy"] = float(-(mixed[i] * np.log(np.maximum(mixed[i], 1e-15))).sum() / np.log(3))
        row["estimator_sd"] = float(scenarios[:, i].std(axis=0, ddof=1).max())
        row["favorite_stability"] = float(np.mean(scenarios[:, i].argmax(axis=1) == mixed[i].argmax()))
    if len(coupon["budgets"]) != 1:
        raise ValueError("Use one predeclared budget.")
    budget = next(iter(coupon["budgets"].values()))["budget_eur"]
    if not 1.5 <= budget <= 5:
        raise ValueError("Budget must stay within 1.50–5.00 EUR.")
    coupon["budgets"] = {f"{budget:.2f}": compare_strategies(mixed.tolist(), scenarios, budget)}
    coupon["market_comparison"] = compare_snapshot(coupon, snapshot, now.isoformat())
    coupon["label"] = observation["label"] + " · candidato con cuotas 50%"
    coupon["model"]["model"] = "Fixed model/market convex pool; base model kept unchanged"
    coupon["model"]["market_pool"] = {"weight": config["market_weight"], "applied_positions": applied,
                                     "women_kept_on_base": retained, "base_forecast_sha256": digest(args.base_forecast)}
    uncertainty = "Conditional bootstrap of the base coefficients with market probabilities held fixed; ignores market uncertainty and is not a calibrated confidence interval"
    coupon["model"]["uncertainty"] = uncertainty
    coupon["model"]["limitations"].extend([uncertainty, "Pleno and expected goals retain the base goal model; 1X2 odds do not calibrate score probabilities"])
    report.update({"config": config, "created_at": now.isoformat(), "prospective": False,
                   "registration_status": "unregistered_separate_market_pool_challenger", "official_contest": observation,
                   "official_order_verified": True, "full_ticket_roi_eligible": True,
                   "positive_expected_roi_demonstrated": False})
    for path in (args.config, args.base_forecast, args.scenarios, args.snapshot, args.official_observation):
        report["inputs"][str(path.resolve())] = digest(path)
    for path in [*list((ROOT / "src").rglob("*.py")), Path(__file__).resolve()]:
        report["source_sha256"][str(path.relative_to(ROOT))] = digest(path)
    if datetime.now(UTC) >= instant(observation["closes_at"]):
        raise ValueError("The contest closed during calculation; nothing is registered.")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    with (args.output_dir / "forecast.json").open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
    with (args.output_dir / "scenarios.npz").open("xb") as handle:
        np.savez_compressed(handle, probabilities=scenarios)
    pd.DataFrame(coupon["fixtures"]).to_parquet(args.output_dir / "predictions.parquet", index=False)
    render_dashboard(report, {}, {}, args.output_dir / "dashboard.html")
    print(json.dumps({"forecast": str(args.output_dir), "pooled_positions": applied, "women_kept_on_base": retained,
                      "registered": False, "roi_demonstrated": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
