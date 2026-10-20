"""Validate a coupon and freeze forecasts before its declared submission date."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from quantfootball.data.competitions import validate_competitions, women_team_name
from quantfootball.data.teams import canonicalize_team
from quantfootball.models.dixon_coles import DixonColesModel, blend_probabilities
from quantfootball.models.elo import EloModel
from quantfootball.quiniela.coverage import best_columns, best_full_system, column_budget


def validate_fixtures(fixtures: pd.DataFrame) -> pd.DataFrame:
    required = {"position", "date", "home_team", "away_team"}
    if not required.issubset(fixtures.columns):
        raise ValueError(f"Fixtures require columns: {sorted(required)}")
    if len(fixtures) != 14 or fixtures["position"].tolist() != list(range(1, 15)):
        raise ValueError("Supply exactly 14 fixtures ordered by position 1 through 14.")
    frame = fixtures.copy()
    if "competition_code" in frame:
        validate_competitions(frame)
    for column in ("home_team", "away_team"):
        if not frame[column].map(lambda x: isinstance(x, str) and bool(x.strip())).all():
            raise ValueError("Every fixture must have nonempty team names.")
        frame[column] = frame.apply(
            lambda row, column=column: (
                women_team_name(row[column])
                if row.get("competition_code") == "es.w.1"
                else canonicalize_team(row[column])
            ),
            axis=1,
        )
    teams = frame["home_team"].tolist() + frame["away_team"].tolist()
    if len(set(teams)) != 28:
        raise ValueError("A team may appear only once among the 14 coupon fixtures.")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    if frame["date"].isna().any():
        raise ValueError("Every fixture must have a date.")
    if frame["date"].dt.tz is not None:
        raise ValueError("Use local calendar dates without timezone for fixtures.")
    return frame


def forecast_coupon(
    history: pd.DataFrame,
    fixtures: pd.DataFrame,
    cutoff: str,
    *,
    model_name: str = "elo",
    model_config: dict | None = None,
    pleno: dict | None = None,
) -> tuple:
    """Train once; exclude the cutoff date entirely because final-whistle times are absent.

    All fourteen forecasts use this same state. Scores or result fields supplied
    in the fixture file are never used. Unseen teams are rejected, not silently
    given average strength.
    """
    frame = validate_fixtures(fixtures)
    if "competition_code" in history and history.competition_code.nunique() > 1:
        raise ValueError(
            "For mixed divisions use scripts/plan_spain.py with division-specific models."
        )
    boundary = pd.Timestamp(cutoff)
    if pd.isna(boundary) or boundary.tz is not None or boundary != boundary.normalize():
        raise ValueError("Cutoff must be a local calendar date, for example 2026-09-24.")
    if (frame["date"] < boundary).any():
        raise ValueError("Fixture dates must not precede the submission cutoff date.")
    required = {"date", "home_team", "away_team", "result"}
    if not required.issubset(history.columns):
        raise ValueError(f"Historical data require columns: {sorted(required)}")
    data = history.copy()
    data["date"] = pd.to_datetime(data["date"], errors="raise")
    train = data.loc[(data["date"] < boundary) & data["result"].notna()].copy()
    if train.empty:
        raise ValueError("No completed historical matches before the cutoff date.")
    if not train["result"].isin(["H", "D", "A"]).all():
        raise ValueError("Historical result labels must be H, D or A.")
    for column in ("home_team", "away_team"):
        if not train[column].map(lambda x: isinstance(x, str) and bool(x.strip())).all():
            raise ValueError("Historical team names must be nonempty strings.")
        train[column] = train[column].map(canonicalize_team)
    known = set(train["home_team"]) | set(train["away_team"])
    unknown = (set(frame["home_team"]) | set(frame["away_team"])) - known
    if unknown:
        raise ValueError(f"Teams without training history: {', '.join(sorted(unknown))}")
    if model_name not in ("elo", "advanced"):
        raise ValueError("Model must be elo or advanced.")
    if pleno is not None and model_name != "advanced":
        raise ValueError("Pleno al 15 requires the advanced goal model.")
    model = EloModel(draw_factor=EloModel.estimate_draw_factor(train))
    model.fit(train)
    probabilities = [
        model.predict_proba(row.home_team, row.away_team) for row in frame.itertuples()
    ]
    for column, sign in (("p_home", "H"), ("p_draw", "D"), ("p_away", "A")):
        frame[column] = [p[sign] for p in probabilities]
    metadata = {
        "model": "QF-MATCH-001 Elo-Davidson",
        "training_matches": len(train),
        "training_last_date": train["date"].max().isoformat(),
        "submission_cutoff_date": boundary.date().isoformat(),
        "cutoff_policy": "Only dates strictly before the cutoff; no updates within the coupon.",
        "parameters": {
            name: getattr(model, name)
            for name in ("initial_rating", "k_factor", "home_advantage", "scale", "draw_factor")
        },
    }
    if model_name == "advanced":
        if model_config is None:
            raise ValueError("The advanced model requires a validation-selected configuration.")
        selection_date = pd.Timestamp(model_config["selected_before"])
        if pd.isna(selection_date) or selection_date.tz is not None or selection_date > boundary:
            raise ValueError("Configuration selection uses information after the requested cutoff.")
        dc = DixonColesModel(
            **{key: model_config[key] for key in ("half_life_days", "ridge", "lookback_days")}
        ).fit(train, boundary)
        blended, expected = [], []
        for fixture, elo_probability in zip(frame.itertuples(), probabilities):
            raw = dc.predict_proba(fixture.home_team, fixture.away_team)
            blended.append(
                blend_probabilities(
                    raw, elo_probability, model_config["dc_weight"], model_config["temperature"]
                )
            )
            expected.append(dc.expected_goals(fixture.home_team, fixture.away_team))
        for column, sign in (("p_home", "H"), ("p_draw", "D"), ("p_away", "A")):
            frame[column] = [p[sign] for p in blended]
        frame["expected_home_goals"] = [p[0] for p in expected]
        frame["expected_away_goals"] = [p[1] for p in expected]
        metadata.update(
            {
                "model": "QF-MATCH-004 calibrated Elo + Dixon-Coles ensemble",
                "goal_model": dc.diagnostics,
                "configuration": model_config,
            }
        )
        if pleno is not None:
            if not {"date", "home_team", "away_team"}.issubset(pleno):
                raise ValueError("Pleno requires date, home_team and away_team.")
            for name in ("home_team", "away_team"):
                if not isinstance(pleno[name], str) or not pleno[name].strip():
                    raise ValueError("Pleno team names must be nonempty strings.")
            home, away = (
                canonicalize_team(pleno["home_team"]),
                canonicalize_team(pleno["away_team"]),
            )
            date = pd.Timestamp(pleno["date"])
            if pd.isna(date) or date.tz is not None or date < boundary:
                raise ValueError("Pleno date must be on or after the cutoff date.")
            coupon_teams = set(frame["home_team"]) | set(frame["away_team"])
            if home in coupon_teams or away in coupon_teams:
                raise ValueError("Pleno teams must be distinct from the first fourteen fixtures.")
            distribution = dc.predict_pleno(home, away)
            best = max(distribution, key=distribution.get)
            metadata["pleno_al_15"] = {
                "home_team": home,
                "away_team": away,
                "date": date.date().isoformat(),
                "probabilities": distribution,
                "recommended_score": best,
                "recommended_probability": distribution[best],
                "model": "Dixon-Coles goal model; no ensemble/temperature calibration of scores",
                "validation": "Historical Primera score evaluation; official Pleno performance not established.",
            }
    return frame, metadata


def plan_coupon(predictions: pd.DataFrame, budget: str = "5.00") -> dict:
    frame = validate_fixtures(predictions)
    columns = ["p_home", "p_draw", "p_away"]
    if not set(columns).issubset(frame.columns):
        raise ValueError(f"Predictions require probability columns: {columns}")
    rows = frame[columns].values.tolist()
    limit, price = column_budget(budget)
    full = best_full_system(rows, limit, min_columns=2)
    individual = best_columns(rows, limit)
    for plan in (full, individual):
        cost = plan["column_count"] * price
        plan["cost_eur"] = str(cost.quantize(Decimal("0.01")))
        plan["unspent_eur"] = str(Decimal(str(budget)) - cost)
    optional = [c for c in ("expected_home_goals", "expected_away_goals") if c in frame]
    records = frame[["position", "date", "home_team", "away_team", *columns, *optional]].copy()
    records["date"] = records["date"].dt.strftime("%Y-%m-%d")
    return {
        "schema_version": 1,
        "objective": "Probability of at least one column matching all first 14 results",
        "assumptions": ["Independent match outcomes", "Input probabilities are estimates"],
        "scope": "First 14 matches only. Pleno al 15 and prize returns are not modeled.",
        "budget_eur": str(budget),
        "price_per_column_eur": str(price),
        "maximum_columns": limit,
        "fixtures": records.to_dict(orient="records"),
        "full_system": full,
        "individual_columns": individual,
        "coverage_gain_individual": individual["coverage"] - full["coverage"],
    }
