"""Run the Quant Football Elo-Davidson baseline."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from quantfootball.models.elo import EloModel

DATASET = Path("data/processed/matches.parquet")
TRAIN_END = pd.Timestamp("2025-05-31")
TEST_SEASON = "2025-26"


def load_matches() -> pd.DataFrame:
    if not DATASET.exists():
        raise SystemExit(
            f"{DATASET} does not exist. Run python scripts/build_laliga_dataset.py first."
        )

    path = DATASET.as_posix().replace("'", "''")
    con = duckdb.connect()
    frame = con.execute(
        f"""
        SELECT date, kickoff_time, season, home_team, away_team, result
        FROM read_parquet('{path}')
        ORDER BY date, kickoff_time
        """
    ).df()
    con.close()
    return frame


def main() -> None:
    matches = load_matches()
    train = matches.loc[matches["date"] <= TRAIN_END].copy()
    test = matches.loc[matches["season"] == TEST_SEASON].copy()

    draw_factor = EloModel.estimate_draw_factor(train)
    model = EloModel(
        initial_rating=1500.0,
        k_factor=20.0,
        home_advantage=65.0,
        scale=400.0,
        draw_factor=draw_factor,
    )
    model.fit(train)
    predictions = model.walk_forward(test)

    final_ratings = sorted(model.ratings.items(), key=lambda item: item[1], reverse=True)

    equal_strength = EloModel(
        home_advantage=model.home_advantage,
        draw_factor=model.draw_factor,
    ).predict_proba("Home", "Away")

    print("Quant Football — QF-MATCH-001 Elo-Davidson")
    print("=" * 60)
    print(f"Training matches: {len(train):,}")
    print(f"Walk-forward test matches ({TEST_SEASON}): {len(predictions):,}")
    print(f"K factor: {model.k_factor:.1f}")
    print(f"Home advantage: {model.home_advantage:.1f} Elo points")
    print(f"Estimated draw factor: {model.draw_factor:.4f}")
    print()
    print("Equal-rating matchup probabilities with home advantage:")
    print(f"P(Home win): {equal_strength['H']:.4f}")
    print(f"P(Draw):     {equal_strength['D']:.4f}")
    print(f"P(Away win): {equal_strength['A']:.4f}")
    print()
    print("Top 10 final Elo ratings after walk-forward test:")
    for position, (team, rating) in enumerate(final_ratings[:10], start=1):
        print(f"{position:>2}. {team:<32} {rating:>8.1f}")


if __name__ == "__main__":
    main()
