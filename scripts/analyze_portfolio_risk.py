"""Enrich frozen portfolios with exact hit probabilities without changing any picks."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from quantfootball.quiniela.dashboard import render_dashboard
from quantfootball.quiniela.risk import portfolio_risk

ROOT = Path(__file__).resolve().parents[1]


def summarize_risk(coupons):
    names = sorted(
        {
            name
            for c in coupons
            if c.get("official")
            for name in c["budgets"].get("5.00", {}).get("strategies", {})
        }
    )
    result = {}
    for name in names:
        examples = []
        for coupon in coupons:
            if not coupon.get("official") or "5.00" not in coupon["budgets"]:
                continue
            strategy = coupon["budgets"]["5.00"]["strategies"][name]
            actual = [f["sign"] for f in coupon["official"]["fixtures"]]
            best = max(
                sum(a == b for a, b in zip(column["signs"], actual))
                for column in strategy["columns"]
            )
            examples.append((coupon, strategy, best))
        best_hits = np.array([x[2] for x in examples])
        thresholds = {}
        for k in range(10, 15):
            probabilities = np.array([s["risk"]["at_least"][str(k)] for _, s, _ in examples])
            observed = best_hits >= k
            thresholds[str(k)] = {
                "expected_contests": float(probabilities.sum()),
                "observed_contests": int(observed.sum()),
                "mean_probability": float(probabilities.mean()),
                "observed_frequency": float(observed.mean()),
                "brier": float(np.mean((probabilities - observed) ** 2)),
            }
        settlements = [
            c["settlement"][name] for c, _, _ in examples if name in c.get("settlement", {})
        ]
        result[name] = {
            "contests": len(examples),
            "thresholds": thresholds,
            "expected_best_hits_mean": float(
                np.mean([s["risk"]["expected_best_hits"] for _, s, _ in examples])
            ),
            "observed_best_hits_mean": float(best_hits.mean()),
            "observed_best_hits_counts": np.bincount(best_hits, minlength=15).tolist(),
            "positive_cash_return_contests": sum(s["gross_return_eur"] > 0 for s in settlements),
            "positive_net_return_contests": sum(s["net_eur"] > 0 for s in settlements),
            "settled_contests": len(settlements),
        }
    return {
        "strategies": result,
        "budget_eur": 5,
        "interpretation": "Descriptive calibration on the existing, previously inspected conditional cohort; no model or portfolio selection",
        "rare_event_warning": "Few or zero observed high-hit events cannot validate small predicted probabilities",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--scenarios-dir", type=Path)
    parser.add_argument(
        "--evaluation", type=Path, default=ROOT / "outputs/reports/spain_v5/evaluation.json"
    )
    parser.add_argument(
        "--audit", type=Path, default=ROOT / "data/processed/matches_spain.audit.json"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("Use a new output directory; frozen reports are never overwritten.")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True)
    scenario_root = args.scenarios_dir or args.report.parent
    sources = {str(args.report): hashlib.sha256(args.report.read_bytes()).hexdigest()}
    for coupon in report["coupons"]:
        path = scenario_root / f"{coupon['date']}.scenarios.npz"
        if not path.exists() and len(report["coupons"]) == 1:
            path = scenario_root / "scenarios.npz"
        with np.load(path, allow_pickle=False) as archive:
            scenarios = archive["probabilities"]
        sources[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        point = [[f[p] for p in ("p_home", "p_draw", "p_away")] for f in coupon["fixtures"]]
        cache = {}
        for pack in coupon["budgets"].values():
            for strategy in pack["strategies"].values():
                key = tuple(sorted(tuple(c["signs"]) for c in strategy["columns"]))
                if key not in cache:
                    cache[key] = portfolio_risk(point, strategy["columns"], scenarios)
                risk = cache[key]
                if not np.isclose(
                    risk["at_least"]["14"], strategy["coverage"], rtol=1e-9, atol=1e-12
                ):
                    raise ValueError(
                        "Existing coverage differs from the frozen point probabilities."
                    )
                strategy["risk"] = risk
        print(coupon["date"], len(cache), "distinct portfolios analyzed", flush=True)
    report["risk_analysis"] = {
        "created_at": datetime.now(UTC).isoformat(),
        "inputs_sha256": sources,
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__), ROOT / "src/quantfootball/quiniela/risk.py"]
        },
        "selection_changed": False,
        "model_changed": False,
        "calibration": summarize_risk(report["coupons"]),
    }
    with (args.output_dir / "risk_report.json").open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
    evaluation = (
        json.loads(args.evaluation.read_text(encoding="utf-8")) if args.evaluation.exists() else {}
    )
    audit = json.loads(args.audit.read_text(encoding="utf-8")) if args.audit.exists() else {}
    render_dashboard(report, evaluation, audit, args.output_dir / "dashboard.html")
    print(json.dumps(report["risk_analysis"]["calibration"], indent=2))


if __name__ == "__main__":
    main()
