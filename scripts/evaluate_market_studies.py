"""Score already frozen model/market forecasts using completed sporting results."""

import argparse
import json
from pathlib import Path

from quantfootball.market.match_study import evaluate_studies, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sporting-snapshots", type=Path, help="Public league captures to audit abandoned/cancelled sporting exclusions")
    args = parser.parse_args()
    value = evaluate_studies(args.root, args.dataset, sporting_snapshots=args.sporting_snapshots)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save(args.output, value)
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
