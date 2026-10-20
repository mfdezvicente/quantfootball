"""Compare variable stakes under hypothetical stress tables, with no deployment."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from quantfootball.quiniela.economic_research import research_frontier
from quantfootball.quiniela.registry import digest, write_new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forecast", type=Path, required=True)
    parser.add_argument("--scenarios", type=Path, required=True)
    parser.add_argument("--budget", type=float, default=10)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.forecast.read_text(encoding="utf-8"))
    specification = json.loads(args.scenarios.read_text(encoding="utf-8"))
    if specification.get("purpose") != "hypothetical_sensitivity" or not specification.get("limitations"):
        raise ValueError("Explicit hypothetical purpose and limitations are required.")
    if len(report["coupons"]) != 1:
        raise ValueError("Supply one forecast.")
    rows = [[f[k] for k in ("p_home", "p_draw", "p_away")] for f in report["coupons"][0]["fixtures"]]
    result = research_frontier(rows, specification["scenarios"], args.budget)
    result.update(created_at=datetime.now(UTC).isoformat(), specification=specification,
                  inputs_sha256={str(p.resolve()): digest(p) for p in (args.forecast, args.scenarios)})
    result["source_sha256"] = {str(p.resolve()): digest(p) for p in
        [Path(__file__), *sorted((Path(__file__).resolve().parents[1] / "src/quantfootball/quiniela").glob("*.py"))]}
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_new(args.output_dir / "frontier.json", result)
    print(json.dumps({"status": result["status"], "deployment_action": result["deployment_action"],
        "candidate_count": len(result["frontier"]), "hypothetical_cost_eur": result["hypothetical_best"]["cost_eur"],
        "worst_conditional_net_eur": result["hypothetical_best"]["worst_conditional_net_eur"]}, indent=2))


if __name__ == "__main__":
    main()
