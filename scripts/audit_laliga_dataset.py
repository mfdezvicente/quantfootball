"""Audit the processed Quant Football LaLiga dataset."""

from __future__ import annotations

from pathlib import Path

import duckdb

DATASET = Path("data/processed/matches.parquet")
EXPECTED_MATCHES_PER_SEASON = 380


def main() -> None:
    if not DATASET.exists():
        raise SystemExit(
            f"{DATASET} does not exist. Run python scripts/build_laliga_dataset.py first."
        )

    con = duckdb.connect()
    parquet_path = DATASET.as_posix().replace("'", "''")

    print("Quant Football — Data quality audit")
    print("=" * 72)

    rows = con.execute(
        f"""
        SELECT
            season,
            COUNT(*) AS matches,
            COUNT(DISTINCT team) AS teams
        FROM (
            SELECT season, home_team AS team
            FROM read_parquet('{parquet_path}')
            UNION ALL
            SELECT season, away_team AS team
            FROM read_parquet('{parquet_path}')
        )
        GROUP BY season
        ORDER BY season
        """
    ).fetchall()

    print(f"{'season':<10}{'matches':>10}{'teams':>8}{'expected':>11}{'missing':>10}{'status':>9}")
    for season, _team_rows, teams in rows:
        matches = con.execute(
            f"""
            SELECT COUNT(*)
            FROM read_parquet('{parquet_path}')
            WHERE season = ?
            """,
            [season],
        ).fetchone()[0]
        missing = EXPECTED_MATCHES_PER_SEASON - matches
        status = "OK" if missing == 0 else "WARN"
        print(
            f"{season:<10}{matches:>10}{teams:>8}"
            f"{EXPECTED_MATCHES_PER_SEASON:>11}{missing:>10}{status:>9}"
        )

    total_rows = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')"
    ).fetchone()[0]

    canonical_teams = [
        row[0]
        for row in con.execute(
            f"""
            SELECT DISTINCT team
            FROM (
                SELECT home_team AS team FROM read_parquet('{parquet_path}')
                UNION
                SELECT away_team AS team FROM read_parquet('{parquet_path}')
            )
            ORDER BY team
            """
        ).fetchall()
    ]

    raw_teams = con.execute(
        f"""
        SELECT COUNT(DISTINCT team)
        FROM (
            SELECT home_team_raw AS team FROM read_parquet('{parquet_path}')
            UNION
            SELECT away_team_raw AS team FROM read_parquet('{parquet_path}')
        )
        """
    ).fetchone()[0]

    duplicates = con.execute(
        f"""
        SELECT COALESCE(SUM(n - 1), 0)
        FROM (
            SELECT season, date, home_team, away_team, COUNT(*) AS n
            FROM read_parquet('{parquet_path}')
            GROUP BY season, date, home_team, away_team
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]

    missing_names = con.execute(
        f"""
        SELECT COUNT(*)
        FROM read_parquet('{parquet_path}')
        WHERE home_team IS NULL OR away_team IS NULL
           OR TRIM(home_team) = '' OR TRIM(away_team) = ''
        """
    ).fetchone()[0]

    print()
    print(f"Rows: {total_rows:,}")
    print(f"Canonical teams across all seasons: {len(canonical_teams)}")
    print(f"Raw source names across all seasons: {raw_teams}")
    print(f"Duplicate fixtures: {duplicates}")
    print(f"Missing canonical team names: {missing_names}")
    print()
    print("Canonical teams:")
    for team in canonical_teams:
        print(f" - {team}")

    con.close()


if __name__ == "__main__":
    main()
