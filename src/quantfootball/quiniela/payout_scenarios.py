"""Joint cash distributions conditional on fixed prizes; never a prize forecast."""

from decimal import Decimal, InvalidOperation

import numpy as np

from quantfootball.quiniela.coverage import SIGNS, validate_probabilities
from quantfootball.quiniela.risk import _poisson_binomial


def cents(value):
    """Reject fractional cents, missing, negative and nonfinite money."""
    try:
        amount = Decimal(str(value)) * 100
    except InvalidOperation as exc:
        raise ValueError("Money must be a finite nonnegative cent amount.") from exc
    if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value():
        raise ValueError("Money must be a finite nonnegative cent amount.")
    if amount > 10**12:
        raise ValueError("Money exceeds the supported scenario range.")
    return int(amount)


def payout_scenario(rows, columns, prizes_by_hits, cost_eur):
    """Exact joint payout for 1–13 distinct columns and 1–14 independent matches.

    Every hit count must have an explicit prize. Pleno and taxes are excluded.
    Common positions share a single hit count; variable positions are enumerated.
    This retains the dependence of columns, including simultaneous small prizes.
    """
    point = np.asarray(validate_probabilities(rows))
    n = len(point)
    signs = [tuple(c["signs"]) for c in columns]
    if not 1 <= len(signs) <= 13 or len(set(signs)) != len(signs):
        raise ValueError("Use one to thirteen distinct columns.")
    if any(len(c) != n or any(s not in SIGNS for s in c) for c in signs):
        raise ValueError("Each column must contain one valid sign per match.")
    if set(prizes_by_hits) != {str(k) for k in range(n + 1)}:
        raise ValueError("Supply explicit prizes for every hit count, including zero prizes.")
    prizes = np.array([cents(prizes_by_hits[str(k)]) for k in range(n + 1)], dtype=np.int64)
    cost = cents(cost_eur)
    if not 0 < cost <= 1000:
        raise ValueError("Use a positive stake of at most ten euros.")
    picks = np.array([[SIGNS.index(s) for s in c] for c in signs])
    shared = np.all(picks == picks[0], axis=0)
    fixed, variable = np.flatnonzero(shared), np.flatnonzero(~shared)
    common = _poisson_binomial(point[None, fixed, picks[0, fixed]])[0]
    masses = {}
    for start in range(0, 3 ** len(variable), 8192):
        numbers = np.arange(start, min(start + 8192, 3 ** len(variable)))
        weights = np.ones(len(numbers))
        hits = np.zeros((len(numbers), len(picks)), dtype=np.int8)
        for position in variable:
            outcome = numbers % 3
            numbers //= 3
            weights *= point[position, outcome]
            hits += outcome[:, None] == picks[:, position]
        for common_hits, probability in enumerate(common):
            if probability == 0:
                continue
            payouts = prizes[hits + common_hits].sum(axis=1)
            amounts, inverse = np.unique(payouts, return_inverse=True)
            sums = np.bincount(inverse, weights=weights * probability)
            for amount, mass in zip(amounts, sums):
                if mass > 0:
                    masses[int(amount)] = masses.get(int(amount), 0.0) + float(mass)
    if not np.isclose(sum(masses.values()), 1, rtol=0, atol=1e-10):
        raise ArithmeticError("Payout distribution lost probability mass.")
    expected = sum(amount * mass for amount, mass in masses.items()) / 100
    return {
        "method": "Exact shared-position convolution and joint enumeration",
        "cost_eur": cost / 100,
        "probability_any_cash": sum(p for x, p in masses.items() if x > 0),
        "probability_recover_stake": sum(p for x, p in masses.items() if x >= cost),
        "probability_profit": sum(p for x, p in masses.items() if x > cost),
        "probability_break_even": masses.get(cost, 0.0),
        "conditional_expected_gross_eur": expected,
        "conditional_expected_net_eur": expected - cost / 100,
        "conditional_roi": expected / (cost / 100) - 1,
        "gross_pmf": [{"gross_eur": x / 100, "probability": p} for x, p in sorted(masses.items())],
        "limitations": [
            "Fixed hypothetical prizes, independent matches and supplied point probabilities",
            "Not an estimate of future prizes, expected investment ROI or an observed settlement",
            "Outcome-dependent winner counts, revenue, jackpot, Pleno and taxes excluded",
            "Prize scenarios carry no probability weights; no calibrated confidence intervals",
        ],
    }
