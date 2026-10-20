"""Probability evaluation utilities for Quant Football."""

from __future__ import annotations

import numpy as np
import pandas as pd


PROB_COLUMNS = ["p_home", "p_draw", "p_away"]
RESULT_TO_INDEX = {"H": 0, "D": 1, "A": 2}


def _validate_predictions(frame: pd.DataFrame) -> None:
    required = {"result", *PROB_COLUMNS}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if frame.empty:
        raise ValueError("Prediction frame is empty.")

    probabilities = frame[PROB_COLUMNS].to_numpy(dtype=float)
    if np.any(probabilities < 0.0) or np.any(probabilities > 1.0):
        raise ValueError("Probabilities must lie in [0, 1].")

    if not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-8):
        raise ValueError("Each probability row must sum to 1.")

    invalid = set(frame["result"].dropna().unique()).difference(RESULT_TO_INDEX)
    if invalid:
        raise ValueError(f"Unexpected result labels: {sorted(invalid)}")


def multiclass_log_loss(frame: pd.DataFrame, *, eps: float = 1e-15) -> float:
    """Mean negative log-probability assigned to the realized 1X2 outcome."""
    _validate_predictions(frame)
    valid = frame["result"].notna()
    scored = frame.loc[valid]

    probabilities = scored[PROB_COLUMNS].to_numpy(dtype=float)
    targets = np.array([RESULT_TO_INDEX[result] for result in scored["result"]], dtype=int)
    realized = probabilities[np.arange(len(scored)), targets]
    return float(-np.log(np.clip(realized, eps, 1.0)).mean())


def multiclass_brier_score(frame: pd.DataFrame) -> float:
    """Mean multiclass Brier score, summing squared errors across H/D/A."""
    _validate_predictions(frame)
    valid = frame["result"].notna()
    scored = frame.loc[valid]

    probabilities = scored[PROB_COLUMNS].to_numpy(dtype=float)
    targets = np.zeros_like(probabilities)
    target_index = np.array(
        [RESULT_TO_INDEX[result] for result in scored["result"]],
        dtype=int,
    )
    targets[np.arange(len(scored)), target_index] = 1.0
    return float(np.mean(np.sum((probabilities - targets) ** 2, axis=1)))


def accuracy(frame: pd.DataFrame) -> float:
    """Top-probability 1X2 classification accuracy."""
    _validate_predictions(frame)
    valid = frame["result"].notna()
    scored = frame.loc[valid]

    probabilities = scored[PROB_COLUMNS].to_numpy(dtype=float)
    labels = np.array(["H", "D", "A"])
    predicted = labels[np.argmax(probabilities, axis=1)]
    return float(np.mean(predicted == scored["result"].to_numpy()))


def evaluate_probabilities(frame: pd.DataFrame) -> dict[str, float]:
    """Return the core Quant Football probability metrics."""
    return {
        "log_loss": multiclass_log_loss(frame),
        "brier": multiclass_brier_score(frame),
        "accuracy": accuracy(frame),
    }
