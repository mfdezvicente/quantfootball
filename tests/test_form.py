import numpy as np
import pandas as pd
import pytest

from quantfootball.features.form import create_feature_table, feature_columns, forecast_features
from quantfootball.models.form import FormClassifier


def history():
    rng = np.random.default_rng(107)
    rows = []
    for i in range(480):
        date = pd.Timestamp("2017-08-01") + pd.Timedelta(days=2 * i)
        home, away = rng.choice(["A", "B", "C", "D"], 2, replace=False)
        gf, ga = rng.poisson([1.4, 1.1])
        year = date.year - (date.month < 7)
        rows.append(
            {
                "match_id": str(i),
                "date": date,
                "home_team": home,
                "away_team": away,
                "competition_code": "es.1",
                "season": f"{year}-{str(year + 1)[-2:]}",
                "home_goals": gf,
                "away_goals": ga,
                "result": "H" if gf > ga else "A" if gf < ga else "D",
            }
        )
    return pd.DataFrame(rows)


def test_form_features_do_not_use_current_week_or_future_scores():
    data = history()
    first = create_feature_table(data)
    cutoff = pd.Timestamp("2019-10-07")
    changed = data.copy()
    changed.loc[changed.date >= cutoff, ["home_goals", "away_goals"]] = [30, 0]
    changed.loc[changed.date >= cutoff, "result"] = "H"
    second = create_feature_table(changed)
    columns = feature_columns(first)
    mask = first.cutoff <= cutoff
    np.testing.assert_array_equal(first.loc[mask, columns], second.loc[mask, columns])
    assert len(columns) == 52
    assert not set(columns) & {"home_goals", "away_goals", "result"}


def test_forecast_features_equal_historical_weekly_features():
    data = history()
    table = create_feature_table(data)
    cutoff = table.cutoff.iloc[-3]
    fixtures = data[data.match_id.isin(table[table.cutoff == cutoff].match_id)]
    observed = forecast_features(data, fixtures, cutoff)
    expected = table.set_index("match_id").loc[fixtures.match_id, feature_columns(table)]
    np.testing.assert_allclose(observed[expected.columns], expected)


@pytest.mark.parametrize(
    "settings",
    [
        {"kind": "logistic", "C": 0.01},
        {"kind": "boosting", "max_leaf_nodes": 7, "l2_regularization": 10.0},
    ],
)
def test_form_classifier_output_and_future_training_labels(settings):
    table = create_feature_table(history())
    cutoff = pd.Timestamp("2019-10-01")
    target = table[table.date >= cutoff].head(4)
    model = FormClassifier(settings).fit(table, cutoff)
    probabilities = model.predict_proba(target)
    np.testing.assert_allclose(probabilities.sum(axis=1), 1)
    assert np.isfinite(probabilities).all() and (probabilities > 0).all()
    changed = table.copy()
    changed.loc[changed.date >= cutoff, "result"] = "D"
    other = FormClassifier(settings).fit(changed, cutoff)
    np.testing.assert_array_equal(probabilities, other.predict_proba(target))
    assert model.training_last_date < cutoff.isoformat()


def test_form_candidate_integrates_with_common_cutoff_and_bootstrap():
    from quantfootball.models.divisions import forecast_divisions

    data = history()
    fixture = pd.DataFrame(
        [{"date": "2020-04-01", "home_team": "A", "away_team": "B", "competition_code": "es.1"}]
    )
    config = {
        "selected_before": "2019-01-01",
        "divisions": {
            "es.1": {
                "selected_before": "2019-01-01",
                "half_life_days": 365,
                "ridge": 10,
                "lookback_days": 1461,
                "dc_weight": 0.5,
                "temperature": 0.9,
                "form_weight": 0.25,
                "form_temperature": 1.0,
                "form_parameters": {"kind": "logistic", "C": 0.01},
            }
        },
    }
    point, scenarios, metadata = forecast_divisions(data, fixture, "2020-04-01", config, draws=2)
    np.testing.assert_allclose(point[["p_home", "p_draw", "p_away"]].sum(axis=1), 1)
    np.testing.assert_allclose(scenarios.sum(axis=2), 1)
    assert metadata["divisions"]["es.1"]["form_model"]["weight"] == 0.25
    assert metadata["divisions"]["es.1"]["form_model"]["coefficient_fit_cutoff"] < "2020-04-01"
    future = data.iloc[-1:].copy()
    future["date"] = pd.Timestamp("2020-04-01")
    future["home_goals"] = 99
    _, other, _ = forecast_divisions(
        pd.concat([data, future]), fixture, "2020-04-01", config, draws=2
    )
    np.testing.assert_array_equal(scenarios, other)
