"""Register prospective abstentions or render a consolidated read-only paper ledger."""

import argparse
import json
from pathlib import Path

from quantfootball.quiniela.decision import register_decision, verify_decision
from quantfootball.quiniela.tracking import consolidated_report, render_tracking


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register")
    register.add_argument("--observation", type=Path, required=True)
    register.add_argument("--forecast", type=Path)
    register.add_argument("--maximum-budget", type=float, default=10)
    register.add_argument("--root", type=Path, default=Path("outputs/predictions/economic_decisions"))
    verify = sub.add_parser("verify")
    verify.add_argument("--record", type=Path, required=True)
    summary = sub.add_parser("summary")
    summary.add_argument("--legacy-root", type=Path, default=Path("outputs/predictions/registry"))
    summary.add_argument("--decision-root", type=Path, default=Path("outputs/predictions/economic_decisions"))
    summary.add_argument("--output-dir", type=Path, required=True)
    for name in ("probability-evaluation", "market-evaluation", "research-evaluation", "source-audit"):
        summary.add_argument("--" + name, type=Path)
    args = parser.parse_args()
    if args.command == "register":
        result = register_decision(args.observation, args.root, maximum_budget_eur=args.maximum_budget,
                                   forecast_path=args.forecast)
    elif args.command == "verify":
        result = verify_decision(args.record)
    else:
        result = consolidated_report(args.legacy_root, args.decision_root, evidence_files={
            name: getattr(args, name) for name in
            ("probability_evaluation", "market_evaluation", "research_evaluation", "source_audit")})
        render_tracking(result, args.output_dir)
        result = {"output": str(args.output_dir), "cohorts": result["cohorts"], "readiness": result["economic_readiness"]}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
