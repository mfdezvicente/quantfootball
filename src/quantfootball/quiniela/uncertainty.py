"""Coverage strategies evaluated over shared bootstrap parameter scenarios."""

import numpy as np

from quantfootball.quiniela.coverage import (
    SIGNS,
    allocation_frontier,
    best_columns,
    best_full_system,
    column_budget,
    simple_submission_groups,
    threshold_system_frontier,
    validate_probabilities,
)
from quantfootball.quiniela.risk import portfolio_risk


def scenario_coverage(scenarios, columns):
    indices = np.array([[SIGNS.index(s) for s in col["signs"]] for col in columns])
    if len({tuple(x) for x in indices}) != len(indices):
        raise ValueError("Duplicate columns would double-count coverage.")
    return np.stack(
        [scenarios[:, np.arange(scenarios.shape[1]), col].prod(axis=1) for col in indices], axis=1
    )


def compare_strategies(rows, scenarios, budget="5.00"):
    point = np.array(validate_probabilities(rows))
    draws = np.asarray(scenarios, dtype=float)
    if draws.ndim != 3 or draws.shape[1:] != point.shape or len(draws) < 2:
        raise ValueError("Scenarios must have shape (draws, matches, 3).")
    for draw in draws:
        validate_probabilities(draw.tolist())
    count, price = column_budget(budget)
    full = best_full_system(rows, count, min_columns=2)
    individual = best_columns(rows, count)
    systems = {}
    candidates = {}
    for probabilities in [point, draws.mean(axis=0), *draws]:
        system = best_full_system(probabilities.tolist(), count, min_columns=2)
        key = tuple(tuple(s) for s in system["selections"])
        systems[key] = system
        for col in best_columns(probabilities.tolist(), min(count * 4, 1000))["columns"]:
            candidates[tuple(col["signs"])] = col

    def lower(system):
        return float(np.quantile(scenario_coverage(draws, system["columns"]).sum(axis=1), 0.1))

    robust_full = dict(max(systems.values(), key=lower))
    pool = list(candidates.values())
    masses = scenario_coverage(draws, pool)
    chosen, covered = [], np.zeros(len(draws))
    for _ in range(min(count, len(pool))):
        scores = np.quantile(covered[:, None] + masses, 0.1, axis=0)
        scores[chosen] = -np.inf
        index = int(scores.argmax())
        chosen.append(index)
        covered += masses[:, index]
    robust_columns = {"column_count": len(chosen), "columns": [pool[i] for i in chosen]}
    strategies = {
        "full_system": full,
        "individual_columns": individual,
        "robust_full_system": robust_full,
        "robust_columns": robust_columns,
    }
    threshold_frontier = []
    if len(rows) == 14 and count <= 13:
        threshold_frontier = threshold_system_frontier(rows, count, 10)
        strategies["at_least_10_full_system"] = max(
            threshold_frontier, key=lambda p: (p["threshold_probability"], -p["column_count"])
        )
        for plan in threshold_frontier:
            plan["cost_eur"] = float(price * plan["column_count"])
    for name, strategy in strategies.items():
        mass = scenario_coverage(draws, strategy["columns"]).sum(axis=1)
        # All displayed column probabilities refer to the same point forecast.
        for col in strategy["columns"]:
            col["probability"] = float(
                np.prod([point[i, SIGNS.index(s)] for i, s in enumerate(col["signs"])])
            )
        strategy["coverage"] = sum(c["probability"] for c in strategy["columns"])
        strategy["bootstrap_mean_coverage"] = float(mass.mean())
        strategy["bootstrap_p10_coverage"] = float(np.quantile(mass, 0.1))
        strategy["bootstrap_p90_coverage"] = float(np.quantile(mass, 0.9))
        strategy["cost_eur"] = float(price * strategy["column_count"])
        if 2 <= len(strategy["columns"]) <= 13:
            strategy["simple_submission_groups"] = simple_submission_groups(strategy["columns"])
        strategy["optimality"] = (
            "Exact for P(best hits >=10) among complete systems at this budget"
            if name == "at_least_10_full_system"
            else "Exact for independent point probabilities"
            if not name.startswith("robust")
            else "Heuristic over bootstrap candidate pool; no global optimality claim"
        )
        if len(strategy["columns"]) <= 13:
            strategy["risk"] = portfolio_risk(point.tolist(), strategy["columns"], draws)
    return {
        "budget_eur": float(budget),
        "max_columns": count,
        "column_price_eur": float(price),
        "strategies": strategies,
        "allocation_frontier": allocation_frontier(rows, budget),
        "threshold_10_frontier": threshold_frontier,
        "bootstrap_system_candidates": len(systems),
        "bootstrap_column_candidates": len(pool),
        "objective": "Probability that at least one column hits all first 14 results; not expected money",
        "uncertainty_note": "Parameter sensitivity, not a calibrated interval for future performance",
    }
