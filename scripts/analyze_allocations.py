"""Compare exact budget allocations and a >=10 objective on frozen forecasts."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from quantfootball.quiniela.coverage import (
    allocation_frontier,
    column_budget,
    threshold_system_frontier,
)
from quantfootball.quiniela.risk import portfolio_risk
from quantfootball.quiniela.settlement import settle_columns
from quantfootball.quiniela.uncertainty import scenario_coverage


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--scenarios-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=False)
    report = json.loads(a.report.read_text(encoding="utf-8"))
    entries, excluded = [], []
    for c in report["coupons"]:
        rows = [[f[k] for k in ("p_home", "p_draw", "p_away")] for f in c["fixtures"]]
        file = a.scenarios_dir / f"{c['date']}.scenarios.npz"
        scenarios = np.load(file)["probabilities"]
        for budget, pack in c["budgets"].items():
            limit, price = column_budget(budget)
            pack["allocation_frontier"] = allocation_frontier(rows, budget)
            frontier = threshold_system_frontier(rows, limit, 10)
            for plan in frontier:
                plan["cost_eur"] = float(price * plan["column_count"])
            pack["threshold_10_frontier"] = frontier
            plan = max(frontier, key=lambda p: (p["threshold_probability"], -p["column_count"]))
            mass = scenario_coverage(scenarios, plan["columns"]).sum(axis=1)
            plan.update(
                bootstrap_mean_coverage=float(mass.mean()),
                bootstrap_p10_coverage=float(np.quantile(mass, 0.1)),
                bootstrap_p90_coverage=float(np.quantile(mass, 0.9)),
                risk=portfolio_risk(rows, plan["columns"], scenarios),
            )
            pack["strategies"]["at_least_10_full_system"] = plan
        plan = c["budgets"]["5.00"]["strategies"]["at_least_10_full_system"]
        try:
            settlement = settle_columns(
                plan["columns"],
                [f["sign"] for f in c["official"]["fixtures"]],
                c["official"]["prizes"],
                pleno_prediction=c["pleno"]["prediction"],
                pleno_actual=c["pleno"]["actual"],
            )
            c["settlement"]["at_least_10_full_system"] = settlement
            entries.append({"date": c["date"], **settlement})
        except ValueError as error:
            excluded.append({"date": c["date"], "reason": str(error)})
        print("Allocation", c["date"], flush=True)
    cost, revenue = sum(e["cost_eur"] for e in entries), sum(e["gross_return_eur"] for e in entries)
    summary = {
        "coupons": len(entries),
        "cost_eur": cost,
        "gross_return_eur": revenue,
        "net_eur": revenue - cost,
        "roi": revenue / cost - 1 if cost else None,
        "by_season": {},
        "excluded": excluded,
        "scope": "Objective predeclared as P(best hits >=10); evaluated retrospectively, not selected by ROI",
    }
    report["summary"]["at_least_10_full_system"] = summary
    report["allocation_analysis"] = {
        "created_at": datetime.now(UTC).isoformat(),
        "source_report_sha256": hashlib.sha256(a.report.read_bytes()).hexdigest(),
        "objective": "Compare P(14) with exact full-system P(best hits >=10) at each affordable composition",
        "new_threshold_summary": summary,
    }
    (a.output_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )
    print(summary, flush=True)


if __name__ == "__main__":
    main()
