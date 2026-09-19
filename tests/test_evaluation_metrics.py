import pandas as pd
import pytest

from quantfootball.evaluation.metrics import (
    accuracy,
    multiclass_brier_score,
    multiclass_log_loss,
)


def _predictions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "result": ["H", "D", "A"],
            "p_home": [0.8, 0.1, 0.1],
            "p_draw": [0.1, 0.8, 0.1],
            "p_away": [0.1, 0.1, 0.8],
        }
    )


def test_accuracy_for_correct_top_probabilities() -> None:
    assert accuracy(_predictions()) == pytest.approx(1.0)


def test_log_loss_is_positive_and_small_for_good_predictions() -> None:
    score = multiclass_log_loss(_predictions())
    assert 0.0 < score < 0.3


def test_brier_is_small_for_good_predictions() -> None:
    score = multiclass_brier_score(_predictions())
    assert 0.0 < score < 0.1


def test_invalid_probability_sum_is_rejected() -> None:
    frame = _predictions()
    frame.loc[0, "p_home"] = 0.7

    with pytest.raises(ValueError, match="sum to 1"):
        multiclass_log_loss(frame)
