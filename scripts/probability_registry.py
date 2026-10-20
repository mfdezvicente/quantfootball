"""Register paired first-14 forecasts; attach pre-close odds and score later results."""

import argparse
import json
from pathlib import Path

from quantfootball.data.active import resolve_active
from quantfootball.market.prospective import (
    attach_market,
    evaluate_pairs,
    register_pair,
    save,
)

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register")
    for name in ("candidate", "comparator", "observation", "protocol"):
        register.add_argument("--" + name, type=Path, required=True)
    register.add_argument("--root", type=Path, default=ROOT / "outputs/predictions/probability_pairs")
    attach = commands.add_parser("attach-market")
    attach.add_argument("--record", type=Path, required=True)
    attach.add_argument("--comparison", type=Path, required=True)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--root", type=Path, default=ROOT / "outputs/predictions/probability_pairs")
    evaluate.add_argument("--dataset", type=Path, help="Defaults to the hash-verified active snapshot")
    evaluate.add_argument("--output", type=Path, required=True, help="New JSON file; existing evaluations stay immutable")
    evaluate.add_argument("--sporting-snapshots", type=Path, help="Public league captures to audit abandoned/cancelled sporting exclusions")
    args = parser.parse_args()
    try:
        if args.command == "register":
            result = register_pair(args.candidate, args.comparator, args.observation, args.protocol, args.root)
        elif args.command == "attach-market":
            result = attach_market(args.record, args.comparison)
        else:
            args.dataset = args.dataset or resolve_active(ROOT)["dataset"]
            result = evaluate_pairs(args.root, args.dataset, sporting_snapshots=args.sporting_snapshots)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            save(args.output, result)
    except (ValueError, KeyError, OSError, TypeError) as exc:
        parser.exit(2, str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
