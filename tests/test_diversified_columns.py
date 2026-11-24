"""Regression checks for the research search's outcome encoding and marginal gain."""

from importlib.util import module_from_spec, spec_from_file_location
from itertools import product
from math import prod
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location(
    "compare_diversified_columns", ROOT / "scripts/compare_diversified_columns.py"
)
study = module_from_spec(SPEC)
SPEC.loader.exec_module(study)


@pytest.mark.parametrize("threshold", [2, 3, 4])
def test_greedy_marginal_coverage_matches_full_enumeration(threshold):
    probabilities = [[.65, .20, .15], [.39, .30, .31], [.26, .27, .47], [.45, .35, .20]]
    outcomes = list(product(study.SIGNS, repeat=len(probabilities)))
    mass = {
        result: prod(row[study.SIGNS.index(sign)] for row, sign in zip(probabilities, result))
        for result in outcomes
    }
    hit_sets = {
        column: {result for result in outcomes
                 if sum(pick == sign for pick, sign in zip(column, result)) >= threshold}
        for column in outcomes
    }
    plan = study.diversified_columns(probabilities, 13, threshold)
    columns = [tuple(column["signs"]) for column in plan["columns"]]
    assert len(set(columns)) == len(columns) == 13
    assert plan["candidates"] == len(outcomes)
    accounted, used = set(), set()
    for column, gain in zip(columns, plan["marginal_probabilities"], strict=True):
        best = max(sum(mass[r] for r in hit_sets[name] - accounted)
                   for name in outcomes if name not in used)
        assert gain == pytest.approx(best, abs=1e-12)
        used.add(column)
        accounted.update(hit_sets[column])
    assert plan["probability"] == pytest.approx(sum(mass[r] for r in accounted), abs=1e-12)
