"""Fit and inspect the Quant Football naive match-outcome baseline."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from quantfootball.models.naive import NaiveOutcomeModel

DATASET = Path("data/processed/matches.parquet")
TRAIN_END = "2025-05-31"


def main() -> None:
    if not DATASET.exists():
        raise SystemExit(
            f"{DATASET} does not exist. Run python scripts/build_laliga_dataset.py first."
        )

    path = DATASET.as_posix().replace("'", "''")
    con = duckdb.connect()
    train = con.execute(
        f"""
        SELECT result
        FROM read_parquet('{path}')
        WHERE date <= DATE '{TRAIN_END}'
        ORDER BY date
        """
    ).df()
    con.close()

    model = NaiveOutcomeModel.fit(train)
    probabilities = model.predict_proba()

    print("Quant Football — QF-MATCH-000 Naive Baseline")
    print("=" * 52)
    print(f"Training matches: {len(train):,}")
    print(f"P(Home win): {probabilities['H']:.4f}")
    print(f"P(Draw):     {probabilities['D']:.4f}")
    print(f"P(Away win): {probabilities['A']:.4f}")
    print(f"Probability sum: {sum(probabilities.values()):.4f}")


if __name__ == "__main__":
    main()
