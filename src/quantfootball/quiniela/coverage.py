"""Exact coverage optimization under independent match outcomes.

The full-system optimizer considers every feasible Cartesian system of singles,
doubles and triples. The column optimizer finds the globally most probable
distinct columns, which need not form a Cartesian system. Neither models prizes.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from itertools import combinations, product
from math import isfinite, prod

SIGNS = ("1", "X", "2")
MAX_COLUMNS = 1000


def simple_submission_groups(columns):
    """Partition 2–13 columns into groups of 2–8, preserving every original pick.

    Export layout only: no bet is transmitted and channel acceptance is not certified.
    """
    if not 2 <= len(columns) <= 13:
        raise ValueError("Use two to thirteen columns for this submission layout.")
    if len(columns) <= 8:
        return [columns]
    split = min(8, len(columns) - 2)
    return [columns[:split], columns[split:]]


def column_budget(budget: str | float, price: str = "0.75") -> tuple[int, Decimal]:
    """Use decimal money arithmetic and never round a budget up."""
    try:
        amount, unit = Decimal(str(budget)), Decimal(str(price))
    except InvalidOperation as exc:
        raise ValueError("Budget and column price must be numbers.") from exc
    if not amount.is_finite() or not unit.is_finite() or amount <= 0 or unit <= 0:
        raise ValueError("Budget and column price must be positive finite numbers.")
    count = int(amount // unit)
    if count < 2:
        raise ValueError("The planner requires a budget for at least two columns.")
    if count > MAX_COLUMNS:
        raise ValueError(f"This version supports at most {MAX_COLUMNS} columns.")
    return count, unit


def validate_probabilities(rows: list[list[float]]) -> list[tuple[float, ...]]:
    if not 1 <= len(rows) <= 14:
        raise ValueError("Supply probabilities for between 1 and 14 matches.")
    clean = []
    for row in rows:
        if len(row) != 3:
            raise ValueError("Each match must have probabilities in 1/X/2 order.")
        values = tuple(float(p) for p in row)
        if any(not isfinite(p) or p < 0 or p > 1 for p in values):
            raise ValueError("Probabilities must be finite and between zero and one.")
        if abs(sum(values) - 1.0) > 1e-8:
            raise ValueError("Each match's probabilities must sum to one.")
        clean.append(tuple(p / sum(values) for p in values))
    return clean


def _limit(count: int, matches: int) -> int:
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_COLUMNS:
        raise ValueError(f"Column limit must be an integer between 1 and {MAX_COLUMNS}.")
    return min(count, 3**matches)


def best_columns(rows: list[list[float]], max_columns: int) -> dict:
    """Exact top-k via prefix pruning: all prefixes have the same possible suffixes."""
    probabilities = validate_probabilities(rows)
    count = _limit(max_columns, len(probabilities))
    prefixes = [(1.0, ())]
    for row in probabilities:
        candidates = [
            (mass * probability, signs + (sign,))
            for mass, signs in prefixes
            for sign, probability in zip(SIGNS, row)
        ]
        prefixes = sorted(candidates, key=lambda item: (-item[0], item[1]))[:count]
    return {
        "column_count": len(prefixes),
        "coverage": sum(mass for mass, _ in prefixes),
        "columns": [{"signs": list(signs), "probability": mass} for mass, signs in prefixes],
    }


def full_system_frontier(
    rows: list[list[float]], max_columns: int, *, min_columns: int = 1
) -> list:
    """DP on column count, maximizing the product of covered probability per match."""
    probabilities = validate_probabilities(rows)
    limit = _limit(max_columns, len(probabilities))
    if not 1 <= min_columns <= limit:
        raise ValueError("Invalid minimum column count.")
    states = {1: (1.0, ())}
    for row in probabilities:
        ranked = sorted(range(3), key=lambda index: (-row[index], index))
        following = {}
        for columns, (mass, selections) in states.items():
            for size in (1, 2, 3):
                new_count = columns * size
                if new_count > limit:
                    continue
                chosen = tuple(sorted(ranked[:size]))
                candidate = (mass * sum(row[i] for i in chosen), selections + (chosen,))
                if new_count not in following or candidate[0] > following[new_count][0]:
                    following[new_count] = candidate
        states = following
    feasible = [n for n in states if n >= min_columns]
    frontier = []
    for count in sorted(feasible):
        coverage, selections = states[count]
        columns = [
            {
                "signs": [SIGNS[i] for i in combination],
                "probability": prod(row[i] for row, i in zip(probabilities, combination)),
            }
            for combination in product(*selections)
        ]
        frontier.append(
            {
                "column_count": count,
                "coverage": coverage,
                "selections": [[SIGNS[i] for i in selected] for selected in selections],
                "singles": sum(len(s) == 1 for s in selections),
                "doubles": sum(len(s) == 2 for s in selections),
                "triples": sum(len(s) == 3 for s in selections),
                "columns": columns,
            }
        )
    return frontier


def best_full_system(rows: list[list[float]], max_columns: int, *, min_columns: int = 1) -> dict:
    """Global maximum over all feasible complete systems, including their locations."""
    return max(
        full_system_frontier(rows, max_columns, min_columns=min_columns),
        key=lambda p: (p["coverage"], -p["column_count"]),
    )


def allocation_frontier(rows, budget="5.00"):
    """Optimal placements for every feasible double/triple count and column cost.

    A complete system with D doubles and T triples has exactly 2**D * 3**T
    columns. Unique factorization means the DP's count states also exhaust all
    feasible compositions. No estimator-variance threshold is needed.
    """
    limit, price = column_budget(budget)
    full = full_system_frontier(rows, limit, min_columns=2)
    top = best_columns(rows, limit)
    individual = [
        {
            "column_count": n,
            "coverage": sum(c["probability"] for c in top["columns"][:n]),
            "columns": top["columns"][:n],
        }
        for n in range(2, len(top["columns"]) + 1)
    ]
    for family in (full, individual):
        previous_coverage, previous_cost = 0.0, 0.0
        for plan in family:
            plan["cost_eur"] = float(price * plan["column_count"])
            plan["efficient_within_family"] = plan["coverage"] > previous_coverage + 1e-15
            plan["incremental_coverage"] = plan["coverage"] - previous_coverage
            plan["incremental_cost_eur"] = plan["cost_eur"] - previous_cost
            previous_coverage = max(previous_coverage, plan["coverage"])
            previous_cost = plan["cost_eur"]
            if len(rows) == 14 and "selections" in plan:
                masses = [
                    sum(row[SIGNS.index(s)] for s in selection)
                    for row, selection in zip(rows, plan["selections"])
                ]
                plan["threshold_probability"] = _hit_tail(masses, 10)
    return {
        "complete_systems": full,
        "individual_columns": individual,
        "objective": "P(14) under conditional independence, not expected prize return",
    }


def _hit_tail(masses, threshold):
    distribution = [1.0]
    for p in masses:
        following = [0.0] * (len(distribution) + 1)
        for k, value in enumerate(distribution):
            following[k] += value * (1 - p)
            following[k + 1] += value * p
        distribution = following
    return sum(distribution[threshold:])


def threshold_system_frontier(rows, max_columns, threshold=10):
    """Exhaustive optimal complete systems for each composition up to thirteen columns.

    In a Cartesian system the best column's number of hits is the number of
    matches whose result lies in the selected signs. Its distribution is exactly
    Poisson-binomial. Taking each match's most probable signs maximizes every
    upper tail for a fixed location/size; enumerate all feasible locations next.
    """
    probabilities = validate_probabilities(rows)
    limit = _limit(max_columns, len(probabilities))
    if (
        limit > 13
        or not isinstance(threshold, int)
        or isinstance(threshold, bool)
        or not 1 <= threshold <= len(rows)
    ):
        raise ValueError(
            "Threshold optimization supports up to thirteen columns and a valid hit threshold."
        )
    rankings = [sorted(range(3), key=lambda i: (-row[i], i)) for row in probabilities]
    winners = {}
    for doubles, triples in [(d, t) for d in range(len(rows) + 1)
                             for t in range(len(rows) + 1 - d)
                             if 2 <= 2**d * 3**t <= limit]:
        count = 2**doubles * 3**triples
        if count > limit or doubles + triples > len(rows):
            continue
        best = None
        for double_positions in combinations(range(len(rows)), doubles):
            remaining = [i for i in range(len(rows)) if i not in double_positions]
            for triple_positions in combinations(remaining, triples):
                selections = [
                    tuple(
                        sorted(
                            rankings[i][
                                : (
                                    2
                                    if i in double_positions
                                    else 3
                                    if i in triple_positions
                                    else 1
                                )
                            ]
                        )
                    )
                    for i in range(len(rows))
                ]
                masses = [
                    sum(row[j] for j in selection)
                    for row, selection in zip(probabilities, selections)
                ]
                score = _hit_tail(masses, threshold)
                if best is None or score > best[0]:
                    best = (score, selections, masses)
        score, selections, masses = best
        winners[count] = {
            "column_count": count,
            "coverage": prod(masses),
            "threshold": threshold,
            "threshold_probability": score,
            "singles": len(rows) - doubles - triples,
            "doubles": doubles,
            "triples": triples,
            "selections": [[SIGNS[j] for j in selection] for selection in selections],
            "columns": [
                {
                    "signs": [SIGNS[j] for j in selection],
                    "probability": prod(row[j] for row, j in zip(probabilities, selection)),
                }
                for selection in product(*selections)
            ],
            "optimality": "Exact complete-system locations for the chosen hit threshold, at most thirteen columns",
        }
    return [winners[n] for n in sorted(winners)]
