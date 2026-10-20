from itertools import product
from math import comb

import numpy as np
import pytest

from quantfootball.quiniela.coverage import SIGNS, best_columns, best_full_system
from quantfootball.quiniela.risk import portfolio_risk


def brute_force(rows, columns):
    histogram = np.zeros(len(rows) + 1)
    expected = np.zeros(len(rows) + 1)
    for outcome in product(range(3), repeat=len(rows)):
        mass = np.prod([p[s] for p, s in zip(rows, outcome)])
        counts = [sum(SIGNS[s] == c["signs"][i] for i, s in enumerate(outcome)) for c in columns]
        histogram[max(counts)] += mass
        for hits in counts:
            expected[hits] += mass
    return histogram, expected


@pytest.mark.parametrize("matches", [1, 2, 4, 6])
def test_exact_portfolio_distribution_matches_exhaustive_enumeration(matches):
    rng = np.random.default_rng(52)
    rows = rng.dirichlet([2, 1, 1], size=matches).tolist()
    columns = best_columns(rows, min(6, 3**matches))["columns"]
    # Include separated columns rather than only a Cartesian product.
    expected, bets = brute_force(rows, columns)
    risk = portfolio_risk(rows, columns)
    np.testing.assert_allclose(risk["best_hits_pmf"], expected, atol=1e-12)
    np.testing.assert_allclose(risk["expected_columns_by_hits"], bets, atol=1e-12)


def test_single_column_binomial_distribution_and_all_tails():
    risk = portfolio_risk([[0.5, 0.3, 0.2]] * 14, [{"signs": ["1"] * 14}])
    expected = np.array([comb(14, k) * 0.5**14 for k in range(15)])
    np.testing.assert_allclose(risk["best_hits_pmf"], expected)
    for k in range(10, 15):
        assert risk["at_least"][str(k)] == pytest.approx(expected[k:].sum())


def test_complete_system_best_hits_equal_covered_match_count():
    rows = [[0.5, 0.3, 0.2]] * 14
    system = best_full_system(rows, 6)
    q = [
        sum(p[SIGNS.index(s)] for s in selections)
        for p, selections in zip(rows, system["selections"])
    ]
    expected = np.array([1.0])
    for p in q:
        expected = np.convolve(expected, [1 - p, p])
    risk = portfolio_risk(rows, system["columns"])
    np.testing.assert_allclose(risk["best_hits_pmf"], expected, atol=1e-12)
    assert risk["at_least"]["14"] == pytest.approx(system["coverage"])


def test_correlated_columns_are_not_counted_as_independent_bets():
    rows = [[0.5, 0.3, 0.2]] * 14
    columns = [{"signs": ["1"] * 14}, {"signs": ["1"] * 13 + ["X"]}]
    together = portfolio_risk(rows, columns)["at_least"]["10"]
    p1, p2 = [portfolio_risk(rows, [col])["at_least"]["10"] for col in columns]
    assert together < 1 - (1 - p1) * (1 - p2)
    assert together >= max(p1, p2)


def test_scenarios_reproduce_identical_probabilities_and_coverage():
    rows = [[0.5, 0.3, 0.2]] * 14
    columns = best_columns(rows, 6)["columns"]
    risk = portfolio_risk(rows, columns, np.array([rows, rows]))
    for k in range(10, 15):
        assert risk["bootstrap_at_least"][str(k)]["p05"] == pytest.approx(risk["at_least"][str(k)])
        assert risk["bootstrap_at_least"][str(k)]["p95"] == pytest.approx(risk["at_least"][str(k)])
    assert sum(risk["expected_columns_by_hits"]) == pytest.approx(6)


def test_deterministic_outcomes_and_duplicate_rejection():
    rows = [[1, 0, 0]] * 14
    columns = [{"signs": ["1"] * 14}, {"signs": ["X"] * 14}]
    risk = portfolio_risk(rows, columns)
    assert risk["best_hits_pmf"][14] == 1
    assert risk["expected_columns_by_hits"][0] == 1
    with pytest.raises(ValueError):
        portfolio_risk(rows, [columns[0], columns[0]])
    with pytest.raises(ValueError):
        portfolio_risk(rows, [{"signs": ["1"]}])
    with pytest.raises(ValueError):
        portfolio_risk(rows, columns, np.ones((2, 14, 3)))
