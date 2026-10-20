"""Hypothetical portfolio frontier; no forecast of Quiniela prizes or betting advice."""

import numpy as np

from quantfootball.quiniela.coverage import best_columns, column_budget, full_system_frontier
from quantfootball.quiniela.payout_scenarios import cents, payout_scenario
from quantfootball.quiniela.risk import _poisson_binomial


def research_frontier(rows, scenarios, budget=10):
    """Minimax fixed-prize sensitivity over a bounded, explicitly heuristic pool.

    Enumerate every prefix of the P(14) top columns and optimal P(14) complete
    systems for each feasible size. Exact expected payout for each portfolio;
    portfolio search is NOT globally optimal for expected money.
    """
    if not 150 <= cents(budget) <= 1000:
        raise ValueError("Budget must be within 1.50–10 EUR.")
    count, _ = column_budget(budget)
    if not scenarios:
        raise ValueError("At least one explicit hypothetical scenario is required.")
    top = best_columns(rows, count)["columns"]
    candidates = {tuple(tuple(c["signs"]) for c in top[:n]): top[:n] for n in range(2, len(top) + 1)}
    for system in full_system_frontier(rows, count, min_columns=2):
        columns = system["columns"]
        candidates[tuple(tuple(c["signs"]) for c in columns)] = columns
    results = [{"columns": [], "cost_eur": 0, "worst_conditional_net_eur": 0,
                "conditional_net_by_scenario": [0] * len(scenarios)}]
    for columns in candidates.values():
        nets = []
        for scenario in scenarios:
            point = np.asarray(scenario.get("probabilities", rows), dtype=float)
            # Reuse strict public validation, without enumerating cash distributions for every candidate.
            from quantfootball.quiniela.coverage import SIGNS, validate_probabilities
            point = np.asarray(validate_probabilities(point.tolist()))
            if point.shape != (len(rows), 3):
                raise ValueError("Scenario fixture dimensions differ.")
            table = scenario["prizes_by_hits"]
            if set(table) != {str(k) for k in range(len(rows) + 1)}:
                raise ValueError("Explicit prizes for every hit count are required.")
            prizes = np.array([cents(table[str(k)]) / 100 for k in range(len(rows) + 1)])
            total = 0.0
            for col in columns:
                picks = [SIGNS.index(s) for s in col["signs"]]
                total += float(_poisson_binomial(point[None, np.arange(len(rows)), picks])[0] @ prizes)
            nets.append(total - len(columns) * .75)
        results.append({"columns": columns, "cost_eur": len(columns) * .75,
                        "worst_conditional_net_eur": min(nets), "conditional_net_by_scenario": nets})
    winner = max(results, key=lambda r: (r["worst_conditional_net_eur"], -r["cost_eur"]))
    if winner["columns"]:
        winner = {**winner, "scenario_risk": [payout_scenario(s.get("probabilities", rows),
            winner["columns"], s["prizes_by_hits"], winner["cost_eur"]) for s in scenarios]}
    return {"status": "hypothetical_research_only", "deployment_action": "abstain",
            "search": "Heuristic candidate pool; no global monetary optimality claim",
            "hypothetical_best": winner, "frontier": results,
            "limitations": "Fixed payouts ignore outcome-dependent public winners, Pleno and taxes; not an economic validation"}
