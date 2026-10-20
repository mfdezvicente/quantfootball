"""Compare QF-MATCH-000 and QF-MATCH-001 out of sample."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from quantfootball.evaluation.metrics import evaluate_probabilities
from quantfootball.models.elo import EloModel
from quantfootball.models.naive import NaiveOutcomeModel

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


def naive_predictions(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    model = NaiveOutcomeModel.fit(train)
    output = test.copy()
    probabilities = model.predict_proba()
    output["p_home"] = probabilities["H"]
    output["p_draw"] = probabilities["D"]
    output["p_away"] = probabilities["A"]
    return output


def elo_predictions(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    draw_factor = EloModel.estimate_draw_factor(train)
    model = EloModel(
        initial_rating=1500.0,
        k_factor=20.0,
        home_advantage=65.0,
        scale=400.0,
        draw_factor=draw_factor,
    )
    model.fit(train)
    return model.walk_forward(test)


def main() -> None:
    matches = load_matches()
    train = matches.loc[matches["date"] <= TRAIN_END].copy()
    test = matches.loc[matches["season"] == TEST_SEASON].copy()

    naive = naive_predictions(train, test)
    elo = elo_predictions(train, test)

    results = {
        "QF-MATCH-000 Naive": evaluate_probabilities(naive),
        "QF-MATCH-001 Elo-Davidson": evaluate_probabilities(elo),
    }

    print("Quant Football — Out-of-sample model comparison")
    print("=" * 74)
    print(f"Training window end: {TRAIN_END.date()}")
    print(f"Test season: {TEST_SEASON}")
    print(f"Test matches: {len(test):,}")
    print()
    print(f"{'Model':<30}{'Log loss':>12}{'Brier':>12}{'Accuracy':>12}")
    for name, metrics in results.items():
        print(
            f"{name:<30}"
            f"{metrics['log_loss']:>12.4f}"
            f"{metrics['brier']:>12.4f}"
            f"{metrics['accuracy']:>12.2%}"
        )

    naive_metrics = results["QF-MATCH-000 Naive"]
    elo_metrics = results["QF-MATCH-001 Elo-Davidson"]

    print()
    print("Relative change vs naive (negative is better for loss metrics):")
    print(
        "Log loss: "
        f"{(elo_metrics['log_loss'] / naive_metrics['log_loss'] - 1.0):+.2%}"
    )
    print(
        "Brier:    "
        f"{(elo_metrics['brier'] / naive_metrics['brier'] - 1.0):+.2%}"
    )
    print(
        "Accuracy: "
        f"{(elo_metrics['accuracy'] / naive_metrics['accuracy'] - 1.0):+.2%}"
    )


if __name__ == "__main__":
    main()
