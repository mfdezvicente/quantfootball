import numpy as np
import pandas as pd
import pytest
from scipy.stats import poisson

from quantfootball.models.dixon_coles import DixonColesModel, blend_probabilities
from quantfootball.quiniela.planning import forecast_coupon


def known_model(rho=-0.1):
    model = DixonColesModel()
    model.teams = {"Home": 0, "Away": 1}
    model.parameters = np.array([np.log(.8), np.log(1.7 / .8), 0, 0, 0, 0])
    model.rho = rho
    return model


def training_data():
    rng = np.random.default_rng(91)
    rows = []
    for day in range(100):
        home, away = rng.choice(["A", "B", "C", "D"], 2, replace=False)
        rows.append({"date": pd.Timestamp("2023-01-01") + pd.Timedelta(days=day),
                     "home_team": home, "away_team": away,
                     "home_goals": int(rng.poisson(2 if home == "A" else 1.4)),
                     "away_goals": int(rng.poisson(.9))})
    return pd.DataFrame(rows)


@pytest.mark.parametrize("rho", [-0.15, 0, 0.15])
def test_1x2_matches_independently_summed_score_grid(rho):
    model = known_model(rho)
    lh, la = model.expected_goals("Home", "Away")
    grid = np.outer(poisson.pmf(np.arange(40), lh), poisson.pmf(np.arange(40), la))
    grid[0, 0] *= 1 - lh * la * rho
    grid[0, 1] *= 1 + lh * rho
    grid[1, 0] *= 1 + la * rho
    grid[1, 1] *= 1 - rho
    probabilities = model.predict_proba("Home", "Away")
    assert probabilities["H"] == pytest.approx(np.tril(grid, -1).sum(), abs=1e-12)
    assert probabilities["D"] == pytest.approx(np.trace(grid), abs=1e-12)
    assert probabilities["A"] == pytest.approx(np.triu(grid, 1).sum(), abs=1e-12)
    assert sum(probabilities.values()) == pytest.approx(1)


def test_pleno_retains_full_three_plus_tail_and_marginals():
    scores = known_model().predict_pleno("Home", "Away")
    assert len(scores) == 16
    assert min(scores.values()) >= 0
    assert sum(scores.values()) == pytest.approx(1)
    assert sum(p for s, p in scores.items() if s.startswith("M-")) == pytest.approx(poisson.sf(2, 1.7))
    assert scores["M-M"] == pytest.approx(poisson.sf(2, 1.7) * poisson.sf(2, .8))


def test_fit_excludes_cutoff_day_and_future_and_is_valid_for_every_pair():
    data = training_data()
    future = data.copy()
    future["date"] = "2023-05-01"
    future["home_goals"] = 50
    first = DixonColesModel().fit(data, "2023-05-01")
    second = DixonColesModel().fit(pd.concat([data, future]), "2023-05-01")
    np.testing.assert_allclose(first.parameters, second.parameters)
    assert first.rho == pytest.approx(second.rho)
    assert first.diagnostics["converged"]
    for home in ["A", "B", "C", "D", "New"]:
        for away in ["A", "B", "C", "D", "New"]:
            if home != away:
                p = first.predict_pleno(home, away, allow_unknown=True)
                assert min(p.values()) >= 0
                assert sum(p.values()) == pytest.approx(1)


def test_strict_unknown_teams_and_invalid_goals():
    model = DixonColesModel().fit(training_data(), "2023-05-01")
    with pytest.raises(ValueError, match="history"):
        model.predict_proba("New", "A")
    data = training_data()
    data.loc[0, "home_goals"] = -1
    with pytest.raises(ValueError, match="nonnegative"):
        DixonColesModel().fit(data, "2023-05-01")


def test_negative_rho_increases_draws_and_blend_respects_endpoints():
    model = known_model()
    dc = model.predict_proba("Home", "Away")
    independent = model.predict_proba("Home", "Away", correction=False)
    assert dc["D"] > independent["D"]
    assert blend_probabilities(dc, independent, 1, 1) == pytest.approx(dc)
    assert blend_probabilities(dc, independent, 0, 1) == pytest.approx(independent)


def coupon_data():
    data = pd.DataFrame({"home_team": [f"H{i}" for i in range(15)],
                         "away_team": [f"A{i}" for i in range(15)],
                         "date": ["2025-01-01"] * 15,
                         "home_goals": [1, 0, 2] * 5, "away_goals": [0, 1, 2] * 5,
                         "result": ["H", "A", "D"] * 5})
    fixtures = data.iloc[:14].assign(position=range(1, 15), date="2025-02-02")
    config = {"half_life_days": 365, "ridge": 10, "lookback_days": 1461,
              "dc_weight": .5, "temperature": .9, "selected_before": "2024-07-01"}
    return data, fixtures, config


def test_advanced_coupon_pleno_and_configuration_cutoff():
    history, fixtures, config = coupon_data()
    pleno = {"home_team": "H14", "away_team": "A14", "date": "2025-02-02"}
    forecast, meta = forecast_coupon(history, fixtures, "2025-02-01", model_name="advanced",
                                     model_config=config, pleno=pleno)
    assert len(forecast) == 14
    assert np.allclose(forecast[["p_home", "p_draw", "p_away"]].sum(axis=1), 1)
    assert len(meta["pleno_al_15"]["probabilities"]) == 16
    with pytest.raises(ValueError, match="after"):
        forecast_coupon(history, fixtures, "2025-02-01", model_name="advanced",
                        model_config={**config, "selected_before": "2026-01-01"})


def test_advanced_cli_with_pleno(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    history, fixtures, config = coupon_data()
    history.to_parquet(tmp_path / "history.parquet")
    fixtures.to_json(tmp_path / "fixtures.json", orient="records")
    (tmp_path / "config.json").write_text(json.dumps(config))
    (tmp_path / "pleno.json").write_text(json.dumps(
        {"home_team": "H14", "away_team": "A14", "date": "2025-02-02"}
    ))
    script = Path(__file__).resolve().parents[1] / "scripts/plan_quiniela.py"
    run = subprocess.run([sys.executable, str(script), "--fixtures", str(tmp_path / "fixtures.json"),
                          "--dataset", str(tmp_path / "history.parquet"),
                          "--model-config", str(tmp_path / "config.json"),
                          "--pleno", str(tmp_path / "pleno.json"), "--cutoff", "2025-02-01",
                          "--output", str(tmp_path / "plan.json")],
                         capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr
    report = json.loads((tmp_path / "plan.json").read_text())
    assert report["individual_columns"]["cost_eur"] == "4.50"
    assert report["individual_columns"]["coverage_14_and_pleno"] <= report["individual_columns"]["coverage"]
    assert report["inputs"]["model_config"]["sha256"]


def test_weekly_backtest_does_not_learn_results_inside_prediction_week():
    from quantfootball.evaluation.advanced import weekly_predictions

    data = training_data()
    data["match_id"] = [f"match-{i}" for i in range(len(data))]
    data["season"] = "2022-23"
    data["result"] = np.where(data.home_goals > data.away_goals, "H",
                              np.where(data.home_goals < data.away_goals, "A", "D"))
    changed = data.copy()
    future = changed["date"] >= pd.Timestamp("2023-02-27")
    changed.loc[future, ["home_goals", "away_goals"]] = [9, 0]
    changed.loc[future, "result"] = "H"
    options = [{"half_life_days": 365, "ridge": 10}]
    first = weekly_predictions(data, "2023-03-01", "2023-03-06", options)
    second = weekly_predictions(changed, "2023-03-01", "2023-03-06", options)
    pd.testing.assert_frame_equal(first[["model", "p_home", "p_draw", "p_away"]],
                                  second[["model", "p_home", "p_draw", "p_away"]])
