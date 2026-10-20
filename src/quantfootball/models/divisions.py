"""Division-specific models and week-block multiplier bootstrap uncertainty."""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantfootball.data.competitions import validate_competitions
from quantfootball.features.form import create_feature_table, forecast_features
from quantfootball.models.calibration import calibrate_probabilities
from quantfootball.models.dixon_coles import DixonColesModel, blend_probabilities
from quantfootball.models.dynamic_goals import DynamicGoalModel
from quantfootball.models.elo import EloModel
from quantfootball.models.form import FormClassifier
from quantfootball.models.transfer_elo import TransferElo

PROBS = ["p_home", "p_draw", "p_away"]


def _fit_elo(train, week_weights=None):
    if week_weights is None:
        return EloModel(draw_factor=EloModel.estimate_draw_factor(train)).fit(train)
    weeks = train.date - pd.to_timedelta(train.date.dt.dayofweek, unit="D")
    weights = weeks.map(week_weights).to_numpy()
    rate = np.average(train.result.eq("D"), weights=weights)
    model = EloModel(draw_factor=2 * rate / (1 - rate))
    for m, w in zip(train.itertuples(index=False), weights):
        model.k_factor = 20 * w
        model.update(m.home_team, m.away_team, m.result)
    model.k_factor = 20
    return model


def forecast_divisions(
    history, fixtures, cutoff, config, *, draws=32, seed=20260925, allow_cold_start=False
):
    """Freeze all matches at one cutoff. Intervals quantify sensitivity, not guarantees.

    Exponential weights are shared by all matches in each calendar week, then both
    Elo and goal strengths are refitted. Hyperparameters remain fixed. This does not
    model lineups, source revisions or every possible form of model misspecification.
    """
    boundary = pd.Timestamp(cutoff)
    if pd.isna(boundary) or boundary.tz is not None or boundary != boundary.normalize():
        raise ValueError("Cutoff must be a timezone-free calendar date.")
    if isinstance(draws, bool) or not isinstance(draws, int) or draws < 2:
        raise ValueError("Use at least two bootstrap draws.")
    selection_date = pd.Timestamp(config["selected_before"])
    if pd.isna(selection_date) or selection_date.tz is not None or selection_date > boundary:
        raise ValueError("Configuration uses results after the forecast cutoff.")
    frame, data = fixtures.copy().reset_index(drop=True), history.copy()
    for source in (frame, data):
        validate_competitions(source)
        source["date"] = pd.to_datetime(source.date)
    if frame.empty or frame.date.isna().any() or (frame.date < boundary).any():
        raise ValueError("Fixtures must be dated on or after cutoff.")
    data = data[(data.date < boundary) & data.result.notna()].sort_values("date", kind="stable")
    weeks = (data.date - pd.to_timedelta(data.date.dt.dayofweek, unit="D")).unique()
    if not len(weeks):
        raise ValueError("No training history before cutoff.")
    rng = np.random.default_rng(seed)
    multipliers = rng.exponential(size=(draws, len(weeks)))
    multipliers /= multipliers.mean(axis=1, keepdims=True)
    maps = [dict(zip(pd.to_datetime(weeks), row)) for row in multipliers]
    scenarios = np.empty((draws, len(frame), 3))
    point = np.empty((len(frame), 3))
    cold = np.zeros(len(frame), dtype=bool)
    details = {}
    for code, group in frame.groupby("competition_code"):
        train = data[data.competition_code.eq(code)].copy()
        parameters = config["divisions"][code]
        selection_date = pd.Timestamp(parameters["selected_before"])
        if pd.isna(selection_date) or selection_date.tz is not None or selection_date > boundary:
            raise ValueError("Division parameters use future results.")
        settings = {k: parameters[k] for k in ("half_life_days", "ridge", "lookback_days")}
        if train.empty:
            raise ValueError(f"No training data for {code}.")
        goal = DixonColesModel(**settings).fit(train, boundary)
        elo = _fit_elo(train)
        transfer_weight = parameters.get("transfer_weight", 0.0)
        if not np.isfinite(transfer_weight) or not 0 <= transfer_weight <= 1:
            raise ValueError("Invalid transfer mixture weight.")
        transfer = (
            TransferElo(**parameters["transfer_parameters"]).fit(
                data[data.competition_code.isin(["es.1", "es.2"])], boundary
            )
            if transfer_weight
            else None
        )
        fixture_seasons = {}
        recent = train[train.date >= boundary - pd.Timedelta(days=365)]
        counts = pd.concat([recent.home_team, recent.away_team]).value_counts()
        for i, m in group.iterrows():
            cold[i] = m.home_team not in goal.teams or m.away_team not in goal.teams
            can_bridge = transfer is not None and all(
                t in transfer.state for t in (m.home_team, m.away_team)
            )
            if cold[i] and not allow_cold_start and not can_bridge:
                raise ValueError(f"No recent division history: {m.home_team} / {m.away_team}.")
            point[i] = list(
                blend_probabilities(
                    goal.predict_proba(
                        m.home_team, m.away_team, allow_unknown=allow_cold_start or can_bridge
                    ),
                    elo.predict_proba(m.home_team, m.away_team),
                    parameters["dc_weight"],
                    parameters["temperature"],
                ).values()
            )
            year = m.date.year - (m.date.month < 7)
            fixture_seasons[i] = f"{year}-{str(year + 1)[-2:]}"
            if transfer is not None:
                transferred = np.array(
                    list(
                        transfer.predict_proba(
                            m.home_team, m.away_team, code, fixture_seasons[i]
                        ).values()
                    )
                )
                point[i] = (1 - transfer_weight) * point[i] + transfer_weight * transferred
            frame.loc[i, "recent_home_matches"] = counts.get(m.home_team, 0)
            frame.loc[i, "recent_away_matches"] = counts.get(m.away_team, 0)
            frame.loc[i, "expected_home_goals"], frame.loc[i, "expected_away_goals"] = (
                goal.expected_goals(
                    m.home_team, m.away_team, allow_unknown=allow_cold_start or can_bridge
                )
            )
        details[code] = {"configuration": parameters, "goal_model": goal.diagnostics}
        for draw, weights in enumerate(maps):
            boot_goal = DixonColesModel(**settings).fit(train, boundary, week_weights=weights)
            boot_elo = _fit_elo(train, weights)
            boot_transfer = (
                TransferElo(**parameters["transfer_parameters"]).fit(
                    data[data.competition_code.isin(["es.1", "es.2"])], boundary, weights
                )
                if transfer_weight
                else None
            )
            for i, m in group.iterrows():
                scenarios[draw, i] = list(
                    blend_probabilities(
                        boot_goal.predict_proba(
                            m.home_team,
                            m.away_team,
                            allow_unknown=allow_cold_start or bool(transfer_weight),
                        ),
                        boot_elo.predict_proba(m.home_team, m.away_team),
                        parameters["dc_weight"],
                        parameters["temperature"],
                    ).values()
                )
                if boot_transfer is not None:
                    transferred = np.array(
                        list(
                            boot_transfer.predict_proba(
                                m.home_team, m.away_team, code, fixture_seasons[i]
                            ).values()
                        )
                    )
                    scenarios[draw, i] = (1 - transfer_weight) * scenarios[
                        draw, i
                    ] + transfer_weight * transferred
    active_form = {
        code: settings
        for code, settings in config["divisions"].items()
        if settings.get("form_weight", 0) != 0 and code in set(frame.competition_code)
    }
    if active_form:
        if "es.w.1" in active_form:
            raise ValueError("Women's form classifiers require a separate research protocol.")
        men_data = data[data.competition_code.isin(["es.1", "es.2"])]
        men_fixtures = frame[frame.competition_code.isin(["es.1", "es.2"])]
        feature_cache = {}
        for version in {p.get("form_feature_version", 1) for p in active_form.values()}:
            feature_cache[version] = (
                create_feature_table(men_data, version),
                forecast_features(men_data, men_fixtures, boundary, version).set_axis(
                    men_fixtures.index
                ),
            )
        # Use the first active Monday of this calendar month, matching the
        # research protocol's monthly coefficient refits and weekly form updates.
        anchor = boundary - pd.Timedelta(days=boundary.dayofweek)
        for code, parameters in active_form.items():
            feature_table, feature_rows = feature_cache[parameters.get("form_feature_version", 1)]
            active_weeks = feature_table.cutoff[
                feature_table.cutoff.dt.to_period("M") == anchor.to_period("M")
            ]
            coefficient_cutoff = min(anchor, active_weeks.min()) if len(active_weeks) else anchor
            weight = parameters["form_weight"]
            temperature = parameters.get("form_temperature", 1.0)
            if (
                not np.isfinite([weight, temperature]).all()
                or not 0 < weight <= 1
                or temperature <= 0
            ):
                raise ValueError("Invalid form weight or temperature.")
            indices = frame.index[frame.competition_code.eq(code)].to_numpy()
            model = FormClassifier(parameters["form_parameters"]).fit(
                feature_table, coefficient_cutoff
            )

            def blend_form(left, right, weight=weight, temperature=temperature):
                mixed = ((1 - weight) * left + weight * right) ** (1 / temperature)
                return mixed / mixed.sum(axis=1, keepdims=True)

            point[indices] = blend_form(
                point[indices], model.predict_proba(feature_rows.loc[indices])
            )
            details[code]["form_model"] = {
                "parameters": parameters["form_parameters"],
                "weight": weight,
                "temperature": temperature,
                "features": model.columns,
                "coefficient_fit_cutoff": coefficient_cutoff.isoformat(),
                "training_last_date": model.training_last_date,
                "bootstrap_limit": "Resamples classifier fit weights; rolling feature values remain fixed",
            }
            for draw, weights in enumerate(maps):
                fitted = FormClassifier(parameters["form_parameters"]).fit(
                    feature_table, coefficient_cutoff, weights
                )
                scenarios[draw, indices] = blend_form(
                    scenarios[draw, indices], fitted.predict_proba(feature_rows.loc[indices])
                )
    # Pool the dynamic model with the complete incumbent (including optional form),
    # matching the chronological research comparison. Calibrate this final pool.
    for code, group in frame.groupby("competition_code"):
        parameters = config["divisions"][code]
        indices = group.index.to_numpy()
        weight = parameters.get("dynamic_weight", 0.0)
        if not np.isfinite(weight) or not 0 <= weight <= 1:
            raise ValueError("Invalid dynamic mixture weight.")
        if weight:
            train = data[data.competition_code.eq(code)]
            settings = parameters["dynamic_parameters"]
            dynamic = DynamicGoalModel(**settings).fit(train, boundary)
            predicted = np.array([
                list(dynamic.predict_proba(m.home_team, m.away_team,
                     allow_unknown=allow_cold_start or bool(parameters.get("transfer_weight", 0))).values())
                for m in group.itertuples(index=False)
            ])
            point[indices] = (1-weight) * point[indices] + weight * predicted
            for i, m in group.iterrows():
                lh, la = dynamic.expected_goals(m.home_team, m.away_team,
                    allow_unknown=allow_cold_start or bool(parameters.get("transfer_weight", 0)))
                frame.loc[i, "dynamic_expected_home_goals"] = lh
                frame.loc[i, "dynamic_expected_away_goals"] = la
            details[code]["dynamic_goal_model"] = dynamic.diagnostics
            for draw, weights in enumerate(maps):
                boot = DynamicGoalModel(**settings).fit(train, boundary, week_weights=weights)
                predicted = np.array([
                    list(boot.predict_proba(m.home_team, m.away_team,
                         allow_unknown=allow_cold_start or bool(parameters.get("transfer_weight", 0))).values())
                    for m in group.itertuples(index=False)
                ])
                scenarios[draw, indices] = (1-weight) * scenarios[draw, indices] + weight * predicted
        calibration = parameters.get("calibration", {"mode": "identity"})
        if "selected_before" in calibration:
            calibration_cutoff = pd.Timestamp(calibration["selected_before"])
            last_date = pd.Timestamp(calibration["training_last_date"])
            if (pd.isna(calibration_cutoff) or calibration_cutoff.tz is not None
                    or calibration_cutoff > boundary or pd.isna(last_date)
                    or last_date >= calibration_cutoff):
                raise ValueError("Calibration uses invalid or future labels.")
        elif calibration.get("mode", "identity") != "identity":
            raise ValueError("A fitted calibrator must record its chronological cutoff.")
        point[indices] = calibrate_probabilities(point[indices], calibration)
        scenarios[:, indices] = calibrate_probabilities(scenarios[:, indices], calibration)
        details[code]["calibration"] = calibration
    frame[PROBS] = point
    for j, name in enumerate(PROBS):
        frame[f"{name}_low"], frame[f"{name}_high"] = np.quantile(
            scenarios[:, :, j], [0.05, 0.95], axis=0
        )
    frame["entropy"] = -(point * np.log(np.maximum(point, 1e-15))).sum(axis=1) / np.log(3)
    frame["estimator_sd"] = scenarios.std(axis=0, ddof=1).max(axis=1)
    frame["favorite_stability"] = (scenarios.argmax(axis=2) == point.argmax(axis=1)).mean(axis=0)
    frame["cold_start"] = cold
    frame["limited_history"] = (
        frame[["recent_home_matches", "recent_away_matches"]].min(axis=1) < 10
    )
    return (
        frame,
        scenarios,
        {
            "model": "Division-specific goal/Elo/form with optional dynamic states and temporal calibration",
            "cutoff": boundary.date().isoformat(),
            "training_last_date": data.date.max().isoformat(),
            "divisions": details,
            "bootstrap_draws": draws,
            "seed": seed,
            "uncertainty": "5-95% week-weight bootstrap spread; conditional sensitivity, not calibrated confidence bounds",
            "cold_start_policy": "Reject unseen division teams unless explicitly allowed or bridged by configured transfer Elo; neutral goal prior is not calibrated for promotion",
            "limitations": [
                "Independent match outcomes conditional on model draw",
                "No lineups, injuries or public betting shares",
                "Optional transfer Elo mixture only when explicitly configured; it does not transfer goal parameters",
                "Optional form classifiers use fixed rolling features during coefficient bootstrap",
                "Dynamic goal states are penalized point estimates, not a full Bayesian posterior",
                "Temporal calibration parameters remain fixed during bootstrap",
            ],
        },
    )
