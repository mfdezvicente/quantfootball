"""Forward-only weekly research evaluation, not a reconstruction of official coupons."""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantfootball.evaluation.metrics import evaluate_probabilities
from quantfootball.models.dixon_coles import DixonColesModel, blend_probabilities
from quantfootball.models.elo import EloModel
from quantfootball.models.naive import NaiveOutcomeModel

CANDIDATES = [
    {"half_life_days": half_life, "ridge": ridge}
    for half_life in (180.0, 365.0) for ridge in (2.0, 10.0)
]
LABELS = ("H", "D", "A")
PROBS = ("p_home", "p_draw", "p_away")


def weekly_predictions(matches: pd.DataFrame, start: str, end: str, candidates: list) -> pd.DataFrame:
    data = matches.copy()
    data["date"] = pd.to_datetime(data["date"])
    targets = data.loc[(data["date"] >= pd.Timestamp(start)) &
                       (data["date"] < pd.Timestamp(end))].copy()
    if targets.empty:
        raise ValueError("No evaluation matches in the requested period.")
    targets["cutoff"] = targets["date"].dt.normalize() - pd.to_timedelta(
        targets["date"].dt.dayofweek, unit="D"
    )
    rows = []
    for block, (cutoff, fixtures) in enumerate(targets.groupby("cutoff")):
        train = data.loc[data["date"] < cutoff].copy()
        if train.empty:
            raise ValueError("Weekly evaluation needs prior training history.")
        elo = EloModel(draw_factor=EloModel.estimate_draw_factor(train)).fit(train)
        naive = NaiveOutcomeModel.fit(train).predict_proba()
        goals = [DixonColesModel(**candidate).fit(train, cutoff) for candidate in candidates]
        for match in fixtures.itertuples(index=False):
            home, away = match.home_team, match.away_team
            context = {"match_id": match.match_id, "season": match.season,
                       "date": match.date.isoformat(), "cutoff": cutoff.isoformat(),
                       "result": match.result}

            def add(model_id, probabilities, context=context, **extra):
                rows.append({**context, "model": model_id, **extra,
                             **dict(zip(PROBS, [probabilities[s] for s in LABELS]))})

            add("naive", naive)
            add("elo", elo.predict_proba(home, away))
            for i, model in enumerate(goals):
                cold = home not in model.teams or away not in model.teams
                scores = model.predict_pleno(home, away, allow_unknown=True)
                labels = ("0", "1", "2", "M")
                actual = f"{labels[min(int(match.home_goals), 3)]}-{labels[min(int(match.away_goals), 3)]}"
                add(f"dc_{i}", model.predict_proba(home, away, allow_unknown=True),
                    cold_start=cold, pleno_log_loss=float(-np.log(scores[actual])),
                    pleno_correct=max(scores, key=scores.get) == actual,
                    pleno_brier=sum((p - (score == actual)) ** 2 for score, p in scores.items()))
                add(f"poisson_{i}", model.predict_proba(
                    home, away, allow_unknown=True, correction=False), cold_start=cold)
        if block % 10 == 0:
            print(f"{start}..{end}: weekly cutoff {cutoff.date()} ({block + 1} blocks)", flush=True)
    return pd.DataFrame(rows)


def blended_frame(frame: pd.DataFrame, candidate: int, weight: float, temperature: float):
    dc = frame.loc[frame["model"] == f"dc_{candidate}"].set_index("match_id")
    elo = frame.loc[frame["model"] == "elo"].set_index("match_id").reindex(dc.index)
    if elo[list(PROBS)].isna().any().any():
        raise ValueError("Model evaluation rows are not aligned.")
    output = dc.copy()
    values = []
    for d, e in zip(dc[list(PROBS)].to_numpy(), elo[list(PROBS)].to_numpy()):
        values.append(list(blend_probabilities(dict(zip(LABELS, d)), dict(zip(LABELS, e)),
                                               weight, temperature).values()))
    output[list(PROBS)] = values
    output["model"] = "selected"
    return output.reset_index()


def select_configuration(validation: pd.DataFrame, candidates: list) -> tuple:
    scores = []
    for candidate in range(len(candidates)):
        for weight in (0.0, 0.5, 1.0):
            for temperature in (0.9, 1.0, 1.1):
                score = evaluate_probabilities(blended_frame(validation, candidate, weight, temperature))
                scores.append({"candidate": candidate, "dc_weight": weight,
                               "temperature": temperature, **score})
    ranked = sorted(scores, key=lambda item: item["log_loss"])
    winner = ranked[0]
    config = {**candidates[winner["candidate"]], "dc_weight": winner["dc_weight"],
              "temperature": winner["temperature"], "lookback_days": 1461}
    return config, ranked


def summarize(frame: pd.DataFrame) -> dict:
    summary = evaluate_probabilities(frame)
    summary["matches"] = len(frame)
    if "pleno_log_loss" in frame and frame["pleno_log_loss"].notna().all():
        summary["pleno_categories"] = {
            "log_loss": float(frame["pleno_log_loss"].mean()),
            "brier": float(frame["pleno_brier"].mean()),
            "accuracy": float(frame["pleno_correct"].mean()),
            "model": "Standalone DC scores; metrics apply to all historical matches, not official Pleno assignments",
        }
    bins = {}
    for label, column in zip(LABELS, PROBS):
        class_bins = []
        for low in np.arange(0, 1, 0.1):
            mask = (frame[column] >= low) & (frame[column] < low + 0.1 + (1e-12 if low > .89 else 0))
            sub = frame.loc[mask]
            if len(sub):
                class_bins.append({"lower": float(low), "count": len(sub),
                                   "mean_probability": float(sub[column].mean()),
                                   "observed_frequency": float((sub["result"] == label).mean())})
        bins[label] = class_bins
    summary["reliability_bins"] = bins
    return summary


def paired_week_bootstrap(selected: pd.DataFrame, baseline: pd.DataFrame) -> dict:
    """Resample weeks, not individual matches, for a descriptive loss-difference interval."""
    left = selected.set_index("match_id")
    right = baseline.set_index("match_id").reindex(left.index)
    targets = np.array([LABELS.index(s) for s in left["result"]])
    indices = np.arange(len(left))
    delta = -np.log(left[list(PROBS)].to_numpy()[indices, targets])
    delta += np.log(right[list(PROBS)].to_numpy()[indices, targets])
    blocks = pd.DataFrame({"cutoff": left["cutoff"].to_numpy(), "delta": delta}).groupby("cutoff")
    sums, counts = blocks["delta"].sum().to_numpy(), blocks.size().to_numpy()
    rng = np.random.default_rng(20260924)
    draws = rng.integers(0, len(sums), size=(2000, len(sums)))
    estimates = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    return {"mean_log_loss_difference": float(delta.mean()),
            "ci95": np.quantile(estimates, [.025, .975]).tolist(), "bootstrap_weeks": len(sums),
            "interpretation": "Negative favors selected model; exploratory block bootstrap."}
