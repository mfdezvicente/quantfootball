"""Small regularized multiclass calibrators fitted to prior out-of-time forecasts."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import softmax

PROBS = ["p_home", "p_draw", "p_away"]
LABELS = ("H", "D", "A")


def calibrate_probabilities(probabilities, config):
    p = np.asarray(probabilities, dtype=float)
    if p.ndim < 1 or p.shape[-1] != 3 or not np.isfinite(p).all() or (p < 0).any():
        raise ValueError("Calibrator requires finite nonnegative three-class probabilities.")
    if not np.allclose(p.sum(axis=-1), 1, atol=1e-8):
        raise ValueError("Calibrator input rows must sum to one.")
    if config.get("mode", "identity") == "identity":
        return p.copy()
    scale = float(config["logit_scale"])
    bias = np.asarray(config["class_bias"], dtype=float)
    if not np.isfinite(scale) or scale <= 0 or bias.shape != (3,) or not np.isfinite(bias).all():
        raise ValueError("Invalid calibrated logit scale or class bias.")
    return softmax(scale * np.log(np.clip(p, 1e-15, 1)) + bias, axis=-1)


def fit_calibrator(frame, cutoff, *, mode="temperature_bias", precision=50.0):
    """Fit on strictly earlier forecast labels, keeping the identity as the prior.

    Forecasts must themselves have been generated with cutoffs earlier than their
    matches. No random folds are used. All parameters can be serialized to JSON.
    """
    if mode not in {"identity", "temperature", "temperature_bias"}:
        raise ValueError("Unknown calibration mode.")
    boundary = pd.Timestamp(cutoff)
    dates, cuts = pd.to_datetime(frame.date), pd.to_datetime(frame.cutoff)
    if pd.isna(boundary) or boundary.tz is not None or boundary != boundary.normalize():
        raise ValueError("Calibration cutoff must be a timezone-free calendar date.")
    if dates.isna().any() or cuts.isna().any() or (dates < cuts).any():
        raise ValueError("Calibration needs valid chronological out-of-time predictions.")
    if frame.match_id.duplicated().any():
        raise ValueError("Duplicate calibration matches.")
    train = frame.loc[dates < boundary]
    if len(train) < 100 or not set(train.result).issubset(LABELS):
        raise ValueError("Calibration needs at least 100 prior labelled predictions.")
    if not np.isfinite(precision) or precision <= 0:
        raise ValueError("Calibration precision must be positive.")
    p = calibrate_probabilities(train[PROBS].to_numpy(), {"mode": "identity"})
    result = {"mode": mode, "selected_before": boundary.date().isoformat(),
              "fit_matches": len(train), "training_last_date": pd.to_datetime(train.date).max().isoformat(),
              "precision": precision, "logit_scale": 1.0, "class_bias": [0.0, 0.0, 0.0]}
    if mode == "identity":
        return result
    logits = np.log(np.clip(p, 1e-15, 1))
    labels = np.array([LABELS.index(r) for r in train.result])
    target = np.eye(3)[labels]

    def objective(theta):
        scale = np.exp(theta[0])
        bias = theta[1:] - theta[1:].mean()
        predicted = softmax(scale * logits + bias, axis=1)
        loss = -np.log(predicted[np.arange(len(train)), labels]).sum()
        loss += precision * np.sum(theta**2) / 2
        residual = predicted - target
        gradient = np.r_[np.sum(residual * logits) * scale, residual.sum(axis=0)]
        gradient += precision * theta
        return float(loss), gradient

    bounds = [(np.log(0.67), np.log(1.5))]
    bounds += [(-0.5, 0.5) if mode == "temperature_bias" else (0, 0)] * 3
    fit = minimize(objective, np.zeros(4), jac=True, method="L-BFGS-B", bounds=bounds)
    if not fit.success or not np.isfinite(fit.x).all():
        raise RuntimeError(f"Calibration failed: {fit.message}")
    result.update(logit_scale=float(np.exp(fit.x[0])),
                  class_bias=(fit.x[1:] - fit.x[1:].mean()).tolist(), converged=True)
    return result

