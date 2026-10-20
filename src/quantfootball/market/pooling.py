"""Fixed convex model/market probability pool; no fitting on the evaluation cohort."""

import numpy as np


def pool_probabilities(model, market, *, market_weight=0.5):
    left, right = np.asarray(model, dtype=float), np.asarray(market, dtype=float)
    if (not np.isfinite(market_weight) or not 0 <= market_weight <= 1
            or left.ndim < 1 or right.ndim < 1 or left.shape[-1] != 3 or right.shape[-1] != 3):
        raise ValueError("A fixed weight in [0,1] and three-class probability vectors are required.")
    for value in (left, right):
        if not np.isfinite(value).all() or (value < 0).any() or not np.allclose(value.sum(axis=-1), 1, atol=1e-8):
            raise ValueError("Probability vectors must be finite, nonnegative and sum to one.")
    try:
        mixed = (1 - market_weight) * left + market_weight * right
    except ValueError as exc:
        raise ValueError("Model and market probability shapes cannot be broadcast together.") from exc
    return mixed / mixed.sum(axis=-1, keepdims=True)
