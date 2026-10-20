from itertools import combinations, product
from math import prod

import pandas as pd
import pytest

from quantfootball.quiniela.coverage import best_columns, best_full_system, column_budget
from quantfootball.quiniela.planning import forecast_coupon, plan_coupon


def test_five_euros_never_rounds_up_to_seven_columns():
    assert column_budget("5")[0] == 6
    assert column_budget("4.49")[0] == 5
    assert column_budget("4.50")[0] == 6
    for invalid in ("NaN", "Infinity", "-1", "1.49", "abc"):
        with pytest.raises(ValueError):
            column_budget(invalid)


@pytest.mark.parametrize("limit", [1, 2, 3, 4, 6, 8, 9])
def test_column_optimizer_equals_exhaustive_enumeration(limit):
    rows = [[0.5, 0.3, 0.2], [0.25, 0.5, 0.25], [0.4, 0.1, 0.5]]
    exhaustive = sorted((prod(p) for p in product(*rows)), reverse=True)
    result = best_columns(rows, limit)
    assert result["coverage"] == pytest.approx(sum(exhaustive[:limit]))
    assert len({tuple(c["signs"]) for c in result["columns"]}) == limit


@pytest.mark.parametrize("limit", [1, 2, 3, 4, 6, 8, 9])
def test_full_system_equals_exhaustive_search_over_all_sign_subsets(limit):
    rows = [[0.5, 0.3, 0.2], [0.25, 0.5, 0.25], [0.4, 0.1, 0.5]]
    subsets = [s for size in (1, 2, 3) for s in combinations(range(3), size)]
    optimum = max(
        prod(sum(row[i] for i in subset) for row, subset in zip(rows, system))
        for system in product(subsets, repeat=3)
        if prod(len(s) for s in system) <= limit
    )
    result = best_full_system(rows, limit)
    assert result["coverage"] == pytest.approx(optimum)
    assert sum(c["probability"] for c in result["columns"]) == pytest.approx(optimum)
    assert result["column_count"] <= limit
    assert best_columns(rows, limit)["coverage"] >= optimum - 1e-12


def test_zero_probabilities_ties_and_full_coverage():
    assert best_columns([[1, 0, 0], [0, 1, 0]], 6)["coverage"] == 1
    assert best_full_system([[1 / 3] * 3] * 2, 9)["coverage"] == pytest.approx(1)
    assert best_columns([[1 / 3] * 3] * 3, 6) == best_columns([[1 / 3] * 3] * 3, 6)


@pytest.mark.parametrize("rows", [[], [[0.5, 0.5]], [[0.4, 0.4, 0.4]],
                                 [[float("nan"), 0, 1]], [[-0.1, 0.5, 0.6]]])
def test_bad_probabilities_rejected(rows):
    with pytest.raises(ValueError):
        best_columns(rows, 6)
    with pytest.raises(ValueError):
        best_full_system(rows, 6)


def fixtures():
    return pd.DataFrame({
        "position": range(1, 15),
        "date": ["2026-09-26"] * 14,
        "home_team": [f"Home {i}" for i in range(14)],
        "away_team": [f"Away {i}" for i in range(14)],
    })


def history():
    frame = fixtures().drop(columns="position")
    frame["date"] = "2026-09-01"
    frame["result"] = ["H", "D", "A"] * 4 + ["H", "D"]
    return frame


def test_cutoff_and_future_results_cannot_change_any_prediction():
    original, meta = forecast_coupon(history(), fixtures(), "2026-09-24")
    extra = pd.concat([history(), history()], ignore_index=True)
    extra.loc[:13, "date"] = "2026-09-24"
    extra.loc[14:, "date"] = "2026-09-27"
    extra["result"] = "A"
    with_results = fixtures().assign(result="A")
    repeated, repeated_meta = forecast_coupon(
        pd.concat([history(), extra]), with_results, "2026-09-24"
    )
    columns = ["p_home", "p_draw", "p_away"]
    pd.testing.assert_frame_equal(original[columns], repeated[columns])
    assert meta == repeated_meta
    assert meta["training_matches"] == 14


def test_unknown_team_and_invalid_coupon_fail_explicitly():
    coupon = fixtures()
    coupon.loc[0, "home_team"] = "Unknown"
    with pytest.raises(ValueError, match="without training history"):
        forecast_coupon(history(), coupon, "2026-09-24")
    with pytest.raises(ValueError, match="14 fixtures"):
        forecast_coupon(history(), fixtures().iloc[:13], "2026-09-24")
    with pytest.raises(ValueError, match="precede"):
        forecast_coupon(history(), fixtures(), "2026-09-27")
    coupon = fixtures()
    coupon.loc[1, "home_team"] = coupon.loc[0, "home_team"]
    with pytest.raises(ValueError, match="only once"):
        forecast_coupon(history(), coupon, "2026-09-24")


def test_end_to_end_budget_and_coverage():
    predictions, _ = forecast_coupon(history(), fixtures(), "2026-09-24")
    report = plan_coupon(predictions)
    assert report["individual_columns"]["column_count"] == 6
    assert report["individual_columns"]["cost_eur"] == "4.50"
    assert report["individual_columns"]["unspent_eur"] == "0.50"
    assert report["full_system"]["column_count"] <= 6
    assert report["coverage_gain_individual"] >= -1e-12
    assert 0 < report["individual_columns"]["coverage"] < 1


def test_cli_writes_snapshot_and_refuses_overwrite(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "probabilities.json"
    output = tmp_path / "snapshot.json"
    fixtures().assign(p_home=0.5, p_draw=0.3, p_away=0.2).to_json(
        input_path, orient="records"
    )
    command = [sys.executable, str(root / "scripts/plan_quiniela.py"),
               "--probabilities", str(input_path), "--output", str(output)]
    first = subprocess.run(command, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stderr
    snapshot = output.read_bytes()
    report = json.loads(snapshot)
    assert report["individual_columns"]["cost_eur"] == "4.50"
    assert report["source_sha256"]
    assert len(report["inputs"]["input"]["sha256"]) == 64
    second = subprocess.run(command, capture_output=True, text=True, check=False)
    assert second.returncode != 0
    assert output.read_bytes() == snapshot
