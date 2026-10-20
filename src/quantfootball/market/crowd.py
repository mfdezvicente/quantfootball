"""Timestamped public selections and research-only joint mixture distributions."""

import numpy as np

from quantfootball.market.snapshots import instant, key, source_url
from quantfootball.quiniela.coverage import SIGNS, validate_probabilities
from quantfootball.quiniela.risk import _poisson_binomial


def validate_crowd(snapshot, observation, decision_at):
    boundary = instant(decision_at)
    if snapshot.get("is_example") or snapshot.get("kind") != "public_selections":
        raise ValueError("Actual public selections required; bookmaker odds are not public shares.")
    if snapshot["contest_id"] != observation["contest_id"]:
        raise ValueError("Different contest.")
    source_url(snapshot["source_url"])
    if not instant(snapshot["observed_at"]) <= instant(snapshot["published_at"]) <= instant(snapshot["retrieved_at"]) <= boundary < instant(observation["closes_at"]):
        raise ValueError("Public selections were not available before the decision and close.")
    if (boundary - instant(snapshot["observed_at"])).total_seconds() > 48 * 3600:
        raise ValueError("Public selections are older than 48 hours.")
    rows = snapshot["fixtures"]
    if len(rows) != 14 or [r["position"] for r in rows] != list(range(1, 15)):
        raise ValueError("Fourteen ordered public selection rows required.")
    for row, fixture in zip(rows, observation["fixtures"][:14]):
        if key(row) != key(fixture) or boundary >= instant(fixture["starts_at"]):
            raise ValueError("Identity mismatch or already started fixture.")
    validate_probabilities([r["shares_1x2"] for r in rows])
    return {"usable_marginals": True, "joint_distribution_identified": False,
            "limitations": "Marginal percentages do not identify correlations between selections"}


def mixture_hit_distribution(components, weights, actual_signs):
    """Distribution of one public column's hits for a supplied latent mixture.

    Components are hypotheses, not inferred from marginals. A mixture can express
    dependence across positions; never label the independence component as truth.
    """
    weights = np.asarray(weights, dtype=float)
    if (weights.ndim != 1 or len(weights) != len(components) or not len(weights)
            or not np.isfinite(weights).all() or (weights < 0).any()
            or not np.isclose(weights.sum(), 1)):
        raise ValueError("Valid mixture weights summing to one are required.")
    if not 1 <= len(actual_signs) <= 14 or any(s not in SIGNS for s in actual_signs):
        raise ValueError("Valid actual signs required.")
    indices = [SIGNS.index(s) for s in actual_signs]
    result = np.zeros(len(indices) + 1)
    for component, weight in zip(components, weights):
        p = np.asarray(validate_probabilities(component))
        if len(p) != len(indices):
            raise ValueError("Component dimensions differ.")
        result += weight * _poisson_binomial(p[None, np.arange(len(p)), indices])[0]
    return result.tolist()
