import copy

import numpy as np
import pandas as pd
import pytest

from quantfootball.models.transfer_elo import TransferElo
from quantfootball.quiniela.settlement import parse_official_extract


def test_promoted_strength_is_transferred_without_prediction_mutation():
    model = TransferElo(league_gap=200, carryover=0.75, newcomer_penalty=0)
    model.update("Promoted", "Other", "es.2", "2023-24", "H")
    model.update("Incumbent", "TopOther", "es.1", "2023-24", "D")
    before = copy.deepcopy(model.state)
    assert model.rating("Promoted", "es.1", "2024-25") < 1500
    assert model.rating("Promoted", "es.1", "2024-25") == pytest.approx(
        1300 + 0.75 * (before["Promoted"]["rating"] - 1300)
    )
    probabilities = model.predict_proba("Incumbent", "Promoted", "es.1", "2024-25")
    assert sum(probabilities.values()) == pytest.approx(1)
    assert probabilities["H"] > probabilities["A"]
    assert model.state == before


def test_relegated_club_keeps_advantage_over_lower_division_prior():
    model = TransferElo(league_gap=300)
    model.update("Relegated", "Other", "es.1", "2023-24", "A")
    assert model.rating("Relegated", "es.2", "2024-25") > model.center("es.2")


def test_future_results_and_cutoff_day_do_not_change_transfer_fit():
    data = pd.DataFrame(
        [
            {
                "date": "2024-05-01",
                "home_team": "A",
                "away_team": "B",
                "competition_code": "es.2",
                "season": "2023-24",
                "result": "H",
            },
            {
                "date": "2024-08-16",
                "home_team": "A",
                "away_team": "C",
                "competition_code": "es.1",
                "season": "2024-25",
                "result": "A",
            },
        ]
    )
    first = TransferElo().fit(data, "2024-08-16")
    data.loc[1, "result"] = "H"
    second = TransferElo().fit(data, "2024-08-16")
    assert first.state == second.state
    assert "C" not in first.state


@pytest.mark.parametrize(
    "kwargs", [{"league_gap": -1}, {"carryover": 1.2}, {"newcomer_penalty": np.nan}]
)
def test_invalid_transfer_parameters(kwargs):
    with pytest.raises(ValueError):
        TransferElo(**kwargs)


def test_conflicting_payouts_are_not_silently_replaced():
    from pathlib import Path

    raw = (Path(__file__).parent / "fixtures/official_2025-05-25.txt").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="Conflicting"):
        parse_official_extract(raw + "\nQF: 14 Aciertos 273 9.999,00\n", "2025-05-25")


def test_indexed_statistical_format_has_same_result():
    import re
    from pathlib import Path

    raw = (Path(__file__).parent / "fixtures/official_2025-05-25.txt").read_text(encoding="utf-8")
    converted = re.sub(r"^L\d+(?:@P\d+)?:", "QF:", raw, flags=re.MULTILINE)
    assert parse_official_extract(raw, "2025-05-25") == parse_official_extract(
        converted, "2025-05-25"
    )


def test_transfer_forecast_bridge_bootstrap_and_future_isolation():
    from test_spain import configuration, fixture, sample

    from quantfootball.models.divisions import forecast_divisions

    data, config, fixtures = sample(), configuration(), fixture()
    data["season"] = np.where(data.date.dt.month < 7, "2020-21", "2021-22")
    lower = data[data.date < "2021-07-01"].copy()
    lower["competition_code"] = "es.2"
    lower["home_team"] = "Promoted"
    lower["away_team"] = "LowerOther"
    data = pd.concat([data, lower], ignore_index=True)
    fixtures.loc[0, "home_team"] = "Promoted"
    with pytest.raises(ValueError, match="history"):
        forecast_divisions(data, fixtures, "2021-10-01", config, draws=2)
    config["divisions"]["es.1"].update(
        transfer_weight=0.25,
        transfer_parameters={"league_gap": 200, "carryover": 0.75, "newcomer_penalty": 80},
    )
    point, scenarios, _ = forecast_divisions(data, fixtures, "2021-10-01", config, draws=2)
    assert point.cold_start.iloc[0]
    assert np.isfinite(scenarios).all()
    np.testing.assert_allclose(scenarios.sum(axis=2), 1)
    future = data.iloc[:1].copy()
    future["date"] = pd.Timestamp("2021-10-01")
    future["home_goals"] = 999
    future["result"] = "A"
    other, other_scenarios, _ = forecast_divisions(
        pd.concat([data, future]), fixtures, "2021-10-01", config, draws=2
    )
    np.testing.assert_array_equal(scenarios, other_scenarios)
    np.testing.assert_array_equal(point.p_home, other.p_home)


def test_zero_transfer_weight_preserves_original_forecast():
    from test_spain import configuration, fixture, sample

    from quantfootball.models.divisions import forecast_divisions

    config = configuration()
    point, draws, _ = forecast_divisions(sample(), fixture(), "2021-10-01", config, draws=2)
    config["divisions"]["es.1"]["transfer_weight"] = 0
    other, other_draws, _ = forecast_divisions(sample(), fixture(), "2021-10-01", config, draws=2)
    np.testing.assert_array_equal(point.p_home, other.p_home)
    np.testing.assert_array_equal(draws, other_draws)
