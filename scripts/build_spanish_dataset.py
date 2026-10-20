"""Build Primera and Segunda from the downloaded, immutable research sources."""

import argparse
from pathlib import Path

from quantfootball.data.spanish import build_spanish_dataset

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=ROOT / "data/raw/research_20260925")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/processed/matches_spain.parquet"
    )
    parser.add_argument("--as-of", default="2026-09-25")
    args = parser.parse_args()
    report = build_spanish_dataset(args.snapshot, args.output, as_of=args.as_of)
    print(f"Rows: {report['rows']}; source conflicts: {len(report['conflicts'])}")
    for row in report["seasons"]:
        print(row)


if __name__ == "__main__":
    main()
