"""Exact best-column hit distribution under conditionally independent matches.

Columns share the same match outcomes. Their hit counts must not be treated as
independent. Factor common picks, then enumerate only positions where picks differ.
"""

import numpy as np

from quantfootball.quiniela.coverage import SIGNS, validate_probabilities


def _poisson_binomial(probabilities):
    """Batch distributions of sums of independent Bernoulli variables."""
    batch, matches = probabilities.shape
    result = np.zeros((batch, matches + 1))
    result[:, 0] = 1
    for i in range(matches):
        p = probabilities[:, i, None]
        previous = result[:, : i + 1].copy()
        result[:, : i + 1] = previous * (1 - p)
        result[:, 1 : i + 2] += previous * p
    return result


def _distributions(probabilities, columns):
    batch, matches, _ = probabilities.shape
    picks = np.asarray([[SIGNS.index(s) for s in c["signs"]] for c in columns])
    shared = np.all(picks == picks[0], axis=0)
    fixed_positions, variable_positions = np.flatnonzero(shared), np.flatnonzero(~shared)
    common = _poisson_binomial(probabilities[:, fixed_positions, picks[0, fixed_positions]])
    variable = np.zeros((batch, len(variable_positions) + 1))
    # Bounded memory even when all fourteen positions differ between columns.
    for start in range(0, 3 ** len(variable_positions), 8192):
        numbers = np.arange(start, min(start + 8192, 3 ** len(variable_positions)))
        outcomes = np.empty((len(numbers), len(variable_positions)), dtype=np.int8)
        weights = np.ones((batch, len(numbers)))
        for j, position in enumerate(variable_positions):
            outcomes[:, j] = numbers % 3
            numbers //= 3
            weights *= probabilities[:, position, outcomes[:, j]]
        best = np.zeros(len(outcomes), dtype=np.int8)
        for column in picks:
            hits = (outcomes == column[variable_positions]).sum(axis=1)
            best = np.maximum(best, hits)
        for i in range(batch):
            variable[i] += np.bincount(best, weights=weights[i], minlength=variable.shape[1])
    best_distribution = np.stack([np.convolve(a, b) for a, b in zip(common, variable)])
    expected_columns = np.zeros((batch, matches + 1))
    for column in picks:
        expected_columns += _poisson_binomial(probabilities[:, np.arange(matches), column])
    return best_distribution, expected_columns, len(variable_positions)


def portfolio_risk(rows, columns, scenarios=None):
    """Analyze 1–13 distinct columns without fitting to results or changing picks."""
    point = np.asarray(validate_probabilities(rows))
    if not 1 <= len(columns) <= 13:
        raise ValueError("Risk analysis supports one to thirteen columns (budget up to 10 EUR).")
    signs = [tuple(c["signs"]) for c in columns]
    if len(set(signs)) != len(signs):
        raise ValueError("Repeated betting columns are not allowed.")
    if any(len(c) != len(point) or any(s not in SIGNS for s in c) for c in signs):
        raise ValueError("Each column needs one valid sign per match.")
    batch = point[None]
    if scenarios is not None:
        samples = np.asarray(scenarios, dtype=float)
        if samples.ndim != 3 or samples.shape[1:] != point.shape or not 2 <= len(samples) <= 512:
            raise ValueError("Use 2 to 512 parameter scenarios with matching dimensions.")
        for row in samples:
            validate_probabilities(row.tolist())
        batch = np.concatenate([batch, samples], axis=0)
    distribution, expected, variable = _distributions(batch, columns)
    if not np.allclose(distribution.sum(axis=1), 1, atol=1e-10):
        raise ArithmeticError("Hit distribution lost probability mass.")
    tails = np.cumsum(distribution[:, ::-1], axis=1)[:, ::-1]
    result = {
        "method": "Exact common-position convolution and enumeration of differing picks",
        "match_count": len(point),
        "column_count": len(columns),
        "differing_positions": variable,
        "best_hits_pmf": distribution[0].tolist(),
        "at_least": {str(k): float(tails[0, k]) for k in range(10, len(point) + 1)},
        "expected_best_hits": float(distribution[0] @ np.arange(len(point) + 1)),
        "expected_columns_by_hits": expected[0].tolist(),
        "parameter_scenarios": len(batch) - 1,
        "limitations": [
            "Exact calculation conditional on supplied probabilities and independent match outcomes",
            "Shared outcomes across columns are accounted for; columns are not independent",
            "10 or more hits do not guarantee a cash payout, net profit or recovery of the stake",
            "No prize forecasts, expected ROI, or Pleno al 15 success probability are inferred",
        ],
    }
    if len(batch) > 1:
        result["bootstrap_at_least"] = {
            str(k): {
                "mean": float(tails[1:, k].mean()),
                "p05": float(np.quantile(tails[1:, k], 0.05)),
                "p95": float(np.quantile(tails[1:, k], 0.95)),
            }
            for k in range(10, len(point) + 1)
        }
        result["bootstrap_note"] = (
            "Sensitivity to parameter scenarios, not calibrated confidence bounds"
        )
    return result
