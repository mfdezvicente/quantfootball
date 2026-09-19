import pandas as pd
import pytest

from quantfootball.models.naive import NaiveOutcomeModel


def test_naive_model_learns_empirical_frequencies() -> None:
    matches = pd.DataFrame({"result": ["H", "H", "D", "A"]})

    model = NaiveOutcomeModel.fit(matches)

    assert model.home_win_prob == pytest.approx(0.50)
    assert model.draw_prob == pytest.approx(0.25)
    assert model.away_win_prob == pytest.approx(0.25)
    assert sum(model.predict_proba().values()) == pytest.approx(1.0)


def test_naive_model_rejects_empty_results() -> None:
    matches = pd.DataFrame({"result": [None, None]})

    with pytest.raises(ValueError, match="without completed match results"):
        NaiveOutcomeModel.fit(matches)


def test_predict_frame_attaches_probabilities() -> None:
    train = pd.DataFrame({"result": ["H", "D", "A", "H"]})
    fixtures = pd.DataFrame(
        {
            "home_team": ["Real Madrid CF", "FC Barcelona"],
            "away_team": ["Valencia CF", "Sevilla FC"],
        }
    )

    model = NaiveOutcomeModel.fit(train)
    predictions = model.predict_frame(fixtures)

    assert list(predictions["p_home"]) == pytest.approx([0.5, 0.5])
    assert list(predictions["p_draw"]) == pytest.approx([0.25, 0.25])
    assert list(predictions["p_away"]) == pytest.approx([0.25, 0.25])
