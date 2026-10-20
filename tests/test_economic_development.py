import copy
import json
from datetime import timedelta
from itertools import product

import numpy as np
import pandas as pd
import pytest
from test_market_registry import registry_case

from quantfootball.features.context_research import context_table
from quantfootball.market.crowd import mixture_hit_distribution, validate_crowd
from quantfootball.quiniela.coverage import (
    SIGNS,
    best_columns,
    column_budget,
    simple_submission_groups,
    threshold_system_frontier,
)
from quantfootball.quiniela.decision import prepare_decision, register_decision, verify_decision
from quantfootball.quiniela.economic_research import research_frontier
from quantfootball.quiniela.payout_scenarios import payout_scenario
from quantfootball.quiniela.registry import validate_registration
from quantfootball.quiniela.risk import portfolio_risk
from quantfootball.quiniela.tracking import performance


def observation_case():
    now, forecast, obs = registry_case()
    obs["official_order_verified"] = True
    for row in obs["fixtures"]:
        row["gender"] = "men"
    return now, forecast, obs


@pytest.mark.parametrize("n", [3, 4, 5])
def test_thirteen_columns_joint_cash_matches_independent_enumeration(n):
    p = np.random.default_rng(n).dirichlet([3, 2, 1], size=n)
    cols = best_columns(p.tolist(), 13)["columns"]
    prizes = {str(k): k * .75 for k in range(n + 1)}
    actual = payout_scenario(p.tolist(), cols, prizes, 9.75)
    expected = {}
    for outcome in product(range(3), repeat=n):
        prob = np.prod(p[np.arange(n), outcome])
        hits = [sum(SIGNS[s] == c["signs"][i] for i, s in enumerate(outcome)) for c in cols]
        total = sum(hits) * 75
        expected[total] = expected.get(total, 0) + prob
    for row in actual["gross_pmf"]:
        assert row["probability"] == pytest.approx(expected.pop(round(row["gross_eur"] * 100)))
    assert not expected
    risk = portfolio_risk(p.tolist(), cols, np.array([p, p]))
    assert sum(risk["best_hits_pmf"]) == pytest.approx(1)
    assert sum(risk["expected_columns_by_hits"]) == pytest.approx(13)


def test_threshold_frontier_covers_new_compositions_and_cost():
    assert column_budget(10)[0] == 13
    plans = threshold_system_frontier([[.5, .3, .2]] * 14, 13, 10)
    assert {p["column_count"] for p in plans} == {2, 3, 4, 6, 8, 9, 12}
    for plan in plans:
        assert len(plan["columns"]) == plan["column_count"]
        assert plan["column_count"] * .75 <= 10


def test_threshold_optimizer_against_all_sign_subsets():
    rows = np.random.default_rng(17).dirichlet([2, 2, 2], size=4).tolist()
    subsets = [(s,) for s in range(3)] + [(0, 1), (0, 2), (1, 2), (0, 1, 2)]
    brute = {}
    for selections in product(subsets, repeat=4):
        count = int(np.prod([len(s) for s in selections]))
        if not 2 <= count <= 13:
            continue
        probability = 0
        for outcome in product(range(3), repeat=4):
            if sum(s in picks for s, picks in zip(outcome, selections)) >= 3:
                probability += np.prod([p[s] for p, s in zip(rows, outcome)])
        brute[count] = max(brute.get(count, 0), probability)
    optimized = threshold_system_frontier(rows, 13, 3)
    assert {p["column_count"] for p in optimized} == set(brute)
    for plan in optimized:
        assert plan["threshold_probability"] == pytest.approx(brute[plan["column_count"]])


@pytest.mark.parametrize("count", range(2, 14))
def test_submission_groups_never_leave_single_column(count):
    columns = list(range(count))
    groups = simple_submission_groups(columns)
    assert all(2 <= len(g) <= 8 for g in groups)
    assert [column for group in groups for column in group] == columns


def test_old_registry_cap_preserved_new_cap_explicit():
    now, forecast, manifest = registry_case()
    pack = next(iter(forecast["coupons"][0]["budgets"].values()))
    pack["budget_eur"] = 10
    with pytest.raises(ValueError):
        validate_registration(forecast, manifest, now)
    manifest.update(schema_version=2, maximum_budget_eur=10, official_order_verified=True)
    assert validate_registration(forecast, manifest, now) == "sample"
    manifest["maximum_budget_eur"] = float("nan")
    with pytest.raises(ValueError):
        validate_registration(forecast, manifest, now)


def test_abstention_is_zero_not_a_fake_positive_roi(tmp_path):
    now, forecast, obs = observation_case()
    decision = prepare_decision(obs, forecast=forecast, now=now)
    assert decision["action"] == "abstain" and decision["stake_eur"] == 0
    assert decision["expected_net_eur"] is None
    path = tmp_path / "observation.json"
    path.write_text(json.dumps(obs), encoding="utf-8")
    root = tmp_path / "decisions"
    register_decision(path, root)
    assert verify_decision(root / "sample")["action"] == "abstain"
    with pytest.raises(FileExistsError):
        register_decision(path, root)
    (root / "sample/decision.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        verify_decision(root / "sample")


@pytest.mark.parametrize("problem", ["closed", "unverified", "future", "duplicate", "overspend"])
def test_bad_decisions_rejected(problem):
    now, _, obs = observation_case()
    cap = 10
    if problem == "closed":
        obs["closes_at"] = now.isoformat()
    elif problem == "unverified":
        obs["official_order_verified"] = False
    elif problem == "future":
        obs["captured_at"] = (now + timedelta(hours=1)).isoformat()
    elif problem == "duplicate":
        obs["fixtures"][1] = {**obs["fixtures"][0], "position": 2}
    else:
        cap = 10.01
    with pytest.raises(ValueError):
        prepare_decision(obs, maximum_budget_eur=cap, now=now)


def test_out_of_scope_coupon_is_recorded_as_abstention():
    now, _, obs = observation_case()
    obs["fixtures"][0]["competition_code"] = "national_teams"
    decision = prepare_decision(obs, now=now)
    assert "out_of_scope_coupon" in decision["reason_codes"]


def test_money_zero_break_even_and_unknown_prizes():
    cols = [{"signs": ["1"]}]
    rows = [[1, 0, 0]]
    assert payout_scenario(rows, cols, {"0": 0, "1": .75}, .75)["probability_break_even"] == 1
    assert payout_scenario(rows, cols, {"0": 0, "1": 0}, .75)["probability_any_cash"] == 0
    with pytest.raises(ValueError):
        payout_scenario(rows, cols, {"0": 0, "1": None}, .75)


def test_hypothetical_optimizer_can_select_no_bet():
    rows = [[.5, .3, .2]] * 3
    scenarios = [{"prizes_by_hits": {str(i): 0 for i in range(4)}}]
    result = research_frontier(rows, scenarios)
    assert result["hypothetical_best"]["cost_eur"] == 0
    assert result["deployment_action"] == "abstain"
    scenarios[0]["prizes_by_hits"]["3"] = 1000
    result = research_frontier(rows, scenarios)
    assert result["hypothetical_best"]["cost_eur"] <= 10
    assert result["deployment_action"] == "abstain"


def test_ledger_keeps_pending_and_stresses_largest_payout():
    entries = [{"record": str(i), "closes_at": f"2026-10-{i+1:02}T12:00:00Z", "status": "settled",
                "settlement": {"cost_eur": 4.5, "gross_return_eur": gross}} for i, gross in enumerate([0, 20, 0])]
    entries.append({"record": "pending", "status": "pending"})
    result = performance(entries)
    assert result["net_eur"] == 6.5
    assert result["maximum_drawdown_eur"] == 4.5
    assert result["roi_without_largest_payout"] == -1
    assert not result["complete_accounting"]
    assert result["roi_block_bootstrap_95"] is None


def test_moving_block_interval_keeps_real_stakes():
    entries = [{"record": str(i), "closes_at": f"2026-10-{i+1:02}T12:00:00Z", "status": "settled",
                "settlement": {"cost_eur": 9.75, "gross_return_eur": 0}} for i in range(8)]
    result = performance(entries)
    assert result["roi_block_bootstrap_95"] == [-1, -1]
    assert result["maximum_drawdown_eur"] == 78


def test_joint_crowd_mixture_differs_from_same_marginal_independence():
    joint = mixture_hit_distribution([[[1, 0, 0]] * 2, [[0, 1, 0]] * 2], [.5, .5], ["1", "1"])
    independent = mixture_hit_distribution([[[.5, .5, 0]] * 2], [1], ["1", "1"])
    assert joint == [.5, 0, .5]
    assert independent == [.25, .5, .25]


def test_crowd_time_and_bookmaker_rejection():
    now, _, obs = observation_case()
    snapshot = {"kind": "public_selections", "contest_id": obs["contest_id"], "source_url": "https://example.org/public",
                "observed_at": now.isoformat(), "published_at": now.isoformat(), "retrieved_at": now.isoformat(),
                "fixtures": [{**f, "shares_1x2": [.5, .3, .2]} for f in obs["fixtures"][:14]]}
    assert validate_crowd(snapshot, obs, now.isoformat())["usable_marginals"]
    snapshot["retrieved_at"] = (now + timedelta(minutes=1)).isoformat()
    with pytest.raises(ValueError):
        validate_crowd(snapshot, obs, now.isoformat())
    snapshot["kind"] = "bookmaker_odds"
    with pytest.raises(ValueError):
        validate_crowd(snapshot, obs, now.isoformat())


def test_context_features_do_not_read_same_week_results():
    rows = [{"match_id": str(i), "date": pd.Timestamp(date), "competition_code": "es.1",
             "home_team": "A", "away_team": "B", "home_goals": i, "away_goals": 0}
            for i, date in enumerate(["2024-01-01", "2024-01-08", "2024-01-10", "2024-01-15"])]
    history = pd.DataFrame(rows)
    before = context_table(history)
    changed = copy.deepcopy(history)
    changed.loc[1, "home_goals"] = 99
    after = context_table(changed)
    pd.testing.assert_frame_equal(before.iloc[:3], after.iloc[:3])
    assert before.iloc[3].home_transfer_scaled_gf != after.iloc[3].home_transfer_scaled_gf
