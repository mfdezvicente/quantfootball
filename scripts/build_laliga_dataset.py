"""Build the Quant Football historical LaLiga dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

from quantfootball.data.openfootball import DEFAULT_SEASONS, build_laliga_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seasons",
        nargs="+",
        default=list(DEFAULT_SEASONS),
        help="Seasons such as 2023-24 2024-25. Defaults to 2015-16 through 2025-26.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/matches.parquet"),
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Redownload raw OpenFootball JSON even if it already exists locally.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = build_laliga_dataset(
        tuple(args.seasons),
        output_path=args.output,
        force_download=args.force_download,
    )

    seasons = frame["season"].nunique()
    teams = len(set(frame["home_team"]) | set(frame["away_team"]))

    print("Quant Football — LaLiga dataset built")
    print(f"Rows: {len(frame):,}")
    print(f"Seasons: {seasons}")
    print(f"Teams (raw source names): {teams}")
    print(f"Date range: {frame['date'].min().date()} -> {frame['date'].max().date()}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
