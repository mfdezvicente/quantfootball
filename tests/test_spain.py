from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quantfootball.data.openfootball import normalize_payload
from quantfootball.data.spanish import parse_football_txt
from quantfootball.data.teams import canonicalize_team
from quantfootball.models.divisions import forecast_divisions
from quantfootball.models.dixon_coles import DixonColesModel
from quantfootball.quiniela.settlement import parse_official_extract, settle_columns
from quantfootball.quiniela.uncertainty import compare_strategies, scenario_coverage


def sample():
    rng = np.random.default_rng(11)
    rows = []
    for i in range(90):
        a, b = rng.choice(["A", "B", "C", "D"], 2, replace=False)
        h, v = rng.poisson([1.5, 1.0])
        rows.append(
            {
                "date": pd.Timestamp("2021-01-01") + pd.Timedelta(days=i * 3),
                "home_team": a,
                "away_team": b,
                "home_goals": h,
                "away_goals": v,
                "result": "H" if h > v else "A" if h < v else "D",
                "competition_code": "es.1",
            }
        )
    return pd.DataFrame(rows)


def configuration():
    return {
        "selected_before": "2021-01-01",
        "divisions": {
            "es.1": {
                "selected_before": "2021-01-01",
                "half_life_days": 365,
                "ridge": 10,
                "lookback_days": 1461,
                "dc_weight": 0.5,
                "temperature": 1,
            }
        },
    }


def fixture():
    return pd.DataFrame(
        [{"date": "2021-10-01", "home_team": "A", "away_team": "B", "competition_code": "es.1"}]
    )


def test_txt_date_rollover_and_formats():
    raw = "▪ Matchday 1\nFri Aug 13\n 20:00 Team A 2-1 (1-0) Team B\n▪ Matchday 2\nSat Jan 15\n 19:00 Team B v Team A 0-0"
    result = parse_football_txt(raw, "2021-22")["matches"]
    assert result[0]["score"]["ft"] == [2, 1]
    assert result[1]["date"] == "2022-01-15"
    assert result[1]["team1"] == "Team B"


def test_txt_fails_unrecognized_lines():
    with pytest.raises(ValueError):
        parse_football_txt("▪ Matchday 1\nFri Aug 13\n unknown result", "2021-22")


@pytest.mark.parametrize("score", [[1.2, 0], [-1, 0], [True, 0], [float("nan"), 0]])
def test_ingestion_rejects_invalid_goals(score):
    with pytest.raises(ValueError):
        normalize_payload(
            {"matches": [{"team1": "A", "team2": "B", "date": "2024-01-01", "score": score}]},
            "2023-24",
            "es.2",
        )


def test_aliases_keep_reserve_teams_separate():
    assert canonicalize_team("R. Sociedad B") == "Real Sociedad B"
    assert canonicalize_team("R. Sociedad B") != canonicalize_team("Real Sociedad")
    assert canonicalize_team("RC Deportivo La Coruña") == canonicalize_team("RC Deportivo")


@pytest.mark.parametrize("value", ["NaT", "2021-01-01T00:00:00Z"])
def test_invalid_selection_date_rejected(value):
    config = configuration()
    config["selected_before"] = value
    with pytest.raises(ValueError):
        forecast_divisions(sample(), fixture(), "2021-10-01", config, draws=2)


def test_bootstrap_equal_weights_reproduce_fit():
    data = sample()
    weeks = data.date - pd.to_timedelta(data.date.dt.dayofweek, unit="D")
    base = DixonColesModel().fit(data, "2021-10-01")
    other = DixonColesModel().fit(data, "2021-10-01", week_weights=dict.fromkeys(weeks, 1.0))
    np.testing.assert_allclose(base.parameters, other.parameters)
    with pytest.raises(ValueError):
        DixonColesModel().fit(data, "2021-10-01", week_weights={})


def test_division_forecast_future_scores_cannot_change_predictions():
    data, fixtures, config = sample(), fixture(), configuration()
    forecast, draws, meta = forecast_divisions(data, fixtures, "2021-10-01", config, draws=4)
    future = data.iloc[:3].copy()
    future["date"] = pd.Timestamp("2021-10-01")
    future["home_goals"] = 100
    _, other, _ = forecast_divisions(
        pd.concat([data, future]), fixtures, "2021-10-01", config, draws=4
    )
    np.testing.assert_array_equal(draws, other)
    np.testing.assert_allclose(draws.sum(axis=2), 1)
    assert forecast.estimator_sd.iloc[0] > 0
    assert meta["training_last_date"] < "2021-10-01"


def test_division_scope_and_unknown_are_explicit():
    data, fixtures, config = sample(), fixture(), configuration()
    fixtures.loc[0, "gender"] = "women"
    with pytest.raises(ValueError, match="men"):
        forecast_divisions(data, fixtures, "2021-10-01", config, draws=2)
    fixtures = fixture()
    fixtures.loc[0, "home_team"] = "New club"
    with pytest.raises(ValueError, match="history"):
        forecast_divisions(data, fixtures, "2021-10-01", config, draws=2)
    config["selected_before"] = "2022-01-01"
    with pytest.raises(ValueError, match="after"):
        forecast_divisions(data, fixture(), "2021-10-01", config, draws=2)


def test_uncertainty_strategies_budget_and_joint_coverage():
    point = [[0.5, 0.3, 0.2]] * 14
    scenarios = np.array([point, [[0.3, 0.4, 0.3]] * 14])
    result = compare_strategies(point, scenarios)
    for plan in result["strategies"].values():
        assert 1.5 <= plan["cost_eur"] <= 5
        assert plan["column_count"] <= 6
        assert len({tuple(c["signs"]) for c in plan["columns"]}) == plan["column_count"]
        mass = scenario_coverage(scenarios, plan["columns"]).sum(axis=1)
        assert plan["bootstrap_mean_coverage"] == pytest.approx(mass.mean())
    assert (
        result["strategies"]["individual_columns"]["coverage"]
        >= result["strategies"]["full_system"]["coverage"] - 1e-12
    )


def prizes():
    return {str(i): {"winners": 10, "unit_eur": str(i)} for i in range(10, 16)}


def test_settlement_pleno_adds_to_fourteen():
    result = settle_columns(
        [{"signs": ["1"] * 14}], ["1"] * 14, prizes(), pleno_prediction="1-M", pleno_actual="1-M"
    )
    assert result["gross_return_eur"] == 29
    assert result["cost_eur"] == 0.75


def test_missing_prizes_are_unknown_and_zero_is_zero():
    table = prizes()
    table["14"]["unit_eur"] = None
    with pytest.raises(ValueError, match="counterfactual"):
        settle_columns([{"signs": ["1"] * 14}], ["1"] * 14, table)
    table["14"]["unit_eur"] = "0.00"
    result = settle_columns([{"signs": ["1"] * 14}], ["1"] * 14, table)
    assert result["roi"] == -1
    with pytest.raises(ValueError):
        settle_columns([{"signs": ["1"] * 14}], ["1"] * 14, {})


def test_saved_official_stats_match_public_prize_table():
    path = Path(__file__).resolve().parents[1] / "tests/fixtures/official_2025-05-25.txt"
    coupon = parse_official_extract(path.read_text(encoding="utf-8"), "2025-05-25")
    assert len(coupon["fixtures"]) == 14
    assert coupon["prizes"]["14"]["unit_eur"] == "1739.04"
    assert coupon["prizes"]["10"]["unit_eur"] == "0.00"
    assert coupon["pleno"]["actual"] == "0-M"
