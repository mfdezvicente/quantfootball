"""Diagnostic settlement on a declared Sunday window; not expected profitability."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from quantfootball.models.divisions import forecast_divisions
from quantfootball.models.dixon_coles import DixonColesModel
from quantfootball.quiniela.settlement import match_coupon, parse_official_extract, settle_columns
from quantfootball.quiniela.uncertainty import compare_strategies

ROOT = Path(__file__).resolve().parents[1]


def json_frame(frame):
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--draws", type=int, default=32)
    parser.add_argument("--start", default="2025-04-06")
    parser.add_argument("--end", default="2025-05-25")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data/raw/official_coupons")
    parser.add_argument(
        "--allow-cold-start",
        action="store_true",
        help="Explicit neutral goal prior for historical cases with no division history",
    )
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("Choose a new output directory; previous studies are immutable.")
    args.output_dir.mkdir(parents=True)
    dataset = ROOT / "data/processed/matches_spain.parquet"
    data = pd.read_parquet(dataset)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    output = {
        "scope": f"All Sundays {args.start} through {args.end}",
        "window": [args.start, args.end],
        "allow_cold_start": args.allow_cold_start,
        "created_at": datetime.now(UTC).isoformat(),
        "coupons": [],
        "excluded": [],
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "config": config,
        "budget_eur": 5,
        "profitable_edge_demonstrated": False,
        "interpretation": "Retrospective gross returns on a small incomplete calendar sample; not expected ROI",
        "limitations": [
            "Current revised results, not historical source snapshots",
            "No official pre-sale fixture publication timestamps or actual submitted bets",
            "Excludes foreign/women/cup fixtures outside model scope",
            "Excludes administrative draws and postponed fixtures that cannot be matched; conditional cohort, not all live bets",
            "Published unit prizes ignore counterfactual dilution and tax",
            "All dates and exclusions are reported; no strategy selected using these payouts",
        ],
    }
    for day in pd.date_range(args.start, args.end, freq="W-SUN"):
        date = day.date().isoformat()
        files = sorted(args.raw_dir.glob(f"{date}*.txt"))
        text = "\n".join(p.read_text(encoding="utf-8") for p in files)
        try:
            coupon = parse_official_extract(text, date)
            fixtures, pleno = match_coupon(coupon, data)
            if set(coupon["prizes"]) != {str(i) for i in range(10, 16)}:
                raise ValueError("Incomplete official prize table.")
        except ValueError as error:
            output["excluded"].append({"date": date, "reason": str(error)})
            print("Excluded", date, error, flush=True)
            continue
        cutoff = min(fixtures.date.min(), pleno["date"]).date().isoformat()
        predictions, scenarios, metadata = forecast_divisions(
            data, fixtures, cutoff, config, draws=args.draws, allow_cold_start=args.allow_cold_start
        )
        # Pleno is forecast with that division's goal model at the same cutoff.
        settings = config["divisions"][pleno["competition_code"]]
        goal = DixonColesModel(
            **{k: settings[k] for k in ("half_life_days", "ridge", "lookback_days")}
        )
        goal.fit(data[data.competition_code.eq(pleno["competition_code"])], cutoff)
        distribution = goal.predict_pleno(
            pleno["home_team"], pleno["away_team"], allow_unknown=args.allow_cold_start
        )
        pleno_prediction = max(distribution, key=distribution.get)
        budgets = {}
        for cents in (150, 225, 300, 375, 450, 500):
            budget = f"{cents / 100:.2f}"
            budgets[budget] = compare_strategies(
                predictions[["p_home", "p_draw", "p_away"]].values.tolist(), scenarios, budget
            )
        results = {}
        for name, strategy in budgets["5.00"]["strategies"].items():
            results[name] = settle_columns(
                strategy["columns"],
                [f["sign"] for f in coupon["fixtures"]],
                coupon["prizes"],
                pleno_prediction=pleno_prediction,
                pleno_actual=coupon["pleno"]["actual"],
            )
        entry = {
            "date": date,
            "cutoff": cutoff,
            "fixtures": json_frame(predictions),
            "model": metadata,
            "budgets": budgets,
            "settlement": results,
            "pleno": {
                "prediction": pleno_prediction,
                "actual": coupon["pleno"]["actual"],
                "probabilities": distribution,
                "home_team": pleno["home_team"],
                "away_team": pleno["away_team"],
            },
            "official": coupon,
            "sources_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
            "source_urls": sorted(
                {line for line in text.splitlines() if line.startswith("https://")}
            ),
        }
        (args.output_dir / f"{date}.json").write_text(
            json.dumps(entry, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
        )
        output["coupons"].append(entry)
        predictions.to_parquet(args.output_dir / f"{date}.parquet", index=False)
        np.savez_compressed(args.output_dir / f"{date}.scenarios.npz", probabilities=scenarios)
        print(date, {k: v["net_eur"] for k, v in results.items()}, flush=True)
    output["summary"] = {}
    output["eligible_cold_start_fixtures"] = sum(
        sum(f["cold_start"] for f in c["fixtures"]) for c in output["coupons"]
    )
    if output["coupons"]:
        rng = np.random.default_rng(20260925)
        for strategy in output["coupons"][0]["settlement"]:
            costs = np.array([c["settlement"][strategy]["cost_eur"] for c in output["coupons"]])
            returns = np.array(
                [c["settlement"][strategy]["gross_return_eur"] for c in output["coupons"]]
            )
            draws = rng.integers(0, len(costs), size=(2000, len(costs)))
            roi = returns[draws].sum(axis=1) / costs[draws].sum(axis=1) - 1
            output["summary"][strategy] = {
                "coupons": len(costs),
                "cost_eur": float(costs.sum()),
                "gross_return_eur": float(returns.sum()),
                "net_eur": float(returns.sum() - costs.sum()),
                "roi": float(returns.sum() / costs.sum() - 1),
                "coupon_bootstrap_roi90": np.quantile(roi, [0.05, 0.95]).tolist(),
                "interval_warning": "Very small sample; bootstrap cannot estimate unobserved rare jackpots",
            }
            seasons = sorted(
                {int(c["date"][:4]) - (int(c["date"][5:7]) < 7) for c in output["coupons"]}
            )
            output["summary"][strategy]["by_season"] = {}
            for season in seasons:
                selected = [
                    c["settlement"][strategy]
                    for c in output["coupons"]
                    if int(c["date"][:4]) - (int(c["date"][5:7]) < 7) == season
                ]
                cost = sum(s["cost_eur"] for s in selected)
                returned = sum(s["gross_return_eur"] for s in selected)
                output["summary"][strategy]["by_season"][f"{season}-{str(season + 1)[-2:]}"] = {
                    "coupons": len(selected),
                    "cost_eur": round(cost, 2),
                    "gross_return_eur": round(returned, 2),
                    "roi": returned / cost - 1,
                }
    output["source_sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__), *sorted((ROOT / "src/quantfootball").rglob("*.py"))]
    }
    (args.output_dir / "roi.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(output["summary"], indent=2))


if __name__ == "__main__":
    main()
