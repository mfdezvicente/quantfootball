import pandas as pd
import pytest

from quantfootball.models.elo import EloModel


def test_probabilities_sum_to_one() -> None:
    model = EloModel(home_advantage=0.0, draw_factor=0.7)
    probabilities = model.predict_proba("A", "B")
    assert probabilities["H"] == pytest.approx(probabilities["A"])
    assert sum(probabilities.values()) == pytest.approx(1.0)
    assert probabilities["D"] > 0.0


def test_home_advantage_increases_home_probability() -> None:
    neutral = EloModel(home_advantage=0.0)
    with_home_advantage = EloModel(home_advantage=65.0)
    assert with_home_advantage.predict_proba("A", "B")["H"] > neutral.predict_proba("A", "B")["H"]


def test_home_win_moves_ratings_in_opposite_directions() -> None:
    model = EloModel(home_advantage=0.0, k_factor=20.0)
    delta = model.update("A", "B", "H")
    assert delta > 0.0
    assert model.get_rating("A") > 1500.0
    assert model.get_rating("B") < 1500.0
    assert model.get_rating("A") + model.get_rating("B") == pytest.approx(3000.0)


def test_weaker_team_gains_rating_after_draw_against_stronger_team() -> None:
    model = EloModel(home_advantage=0.0)
    model.ratings = {"Weak": 1400.0, "Strong": 1600.0}
    delta = model.update("Weak", "Strong", "D")
    assert delta > 0.0
    assert model.get_rating("Weak") > 1400.0
    assert model.get_rating("Strong") < 1600.0


def test_walk_forward_predicts_before_updating() -> None:
    matches = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-01", "2025-01-08"]),
            "home_team": ["A", "A"],
            "away_team": ["B", "B"],
            "result": ["H", "H"],
        }
    )
    model = EloModel(home_advantage=0.0)
    predictions = model.walk_forward(matches)
    assert predictions.loc[0, "home_rating_pre"] == pytest.approx(1500.0)
    assert predictions.loc[1, "home_rating_pre"] > 1500.0
    assert predictions.loc[1, "p_home"] > predictions.loc[0, "p_home"]


def test_draw_factor_estimation_matches_equal_strength_identity() -> None:
    matches = pd.DataFrame({"result": ["H", "D", "A", "D"]})
    draw_factor = EloModel.estimate_draw_factor(matches)
    assert draw_factor == pytest.approx(2.0)
