"""Audit the processed Quant Football LaLiga dataset."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATASET = Path("data/processed/matches.parquet")
EXPECTED_MATCHES_PER_SEASON = 380


def main() -> None:
    if not DATASET.exists():
        raise SystemExit(
            f"{DATASET} does not exist. Run python scripts/build_laliga_dataset.py first."
        )

    frame = pd.read_parquet(DATASET)

    print("Quant Football — Data quality audit")
    print("=" * 72)

    rows = []
    for season, group in frame.groupby("season", sort=True):
        teams = len(set(group["home_team"]) | set(group["away_team"]))
        matches = len(group)
        status = "OK" if matches == EXPECTED_MATCHES_PER_SEASON else "WARN"
        rows.append(
            {
                "season": season,
                "matches": matches,
                "teams": teams,
                "expected": EXPECTED_MATCHES_PER_SEASON,
                "missing": EXPECTED_MATCHES_PER_SEASON - matches,
                "status": status,
            }
        )

    report = pd.DataFrame(rows)
    print(report.to_string(index=False))
    print()

    canonical_teams = sorted(set(frame["home_team"]) | set(frame["away_team"]))
    raw_teams = sorted(set(frame["home_team_raw"]) | set(frame["away_team_raw"]))

    print(f"Rows: {len(frame):,}")
    print(f"Canonical teams across all seasons: {len(canonical_teams)}")
    print(f"Raw source names across all seasons: {len(raw_teams)}")
    print(f"Duplicate fixtures: {frame.duplicated(['season','date','home_team','away_team']).sum()}")
    print(f"Missing canonical team names: {frame[['home_team','away_team']].isna().sum().sum()}")
    print()
    print("Canonical teams:")
    for team in canonical_teams:
        print(f" - {team}")


if __name__ == "__main__":
    main()
