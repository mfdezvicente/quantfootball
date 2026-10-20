import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from quantfootball.market.snapshots import compare_snapshot, devig, instant
from quantfootball.quiniela.registry import (
    register_forecast,
    registry_summary,
    settle_record,
    validate_registration,
    verify_record,
)


def market_case():
    fixture = {
        "position": 1,
        "competition_code": "es.1",
        "home_team": "A",
        "away_team": "B",
        "date": "2026-09-27",
        "p_home": 0.5,
        "p_draw": 0.3,
        "p_away": 0.2,
    }
    snapshot = {
        "schema_version": 1,
        "snapshot_at": "2026-09-25T10:00:00Z",
        "retrieved_at": "2026-09-25T10:01:00Z",
        "source_url": "https://example.org/odds",
        "fixtures": [
            {
                **fixture,
                "starts_at": "2026-09-27T16:00:00Z",
                "quotes": [
                    {
                        "bookmaker": "one",
                        "observed_at": "2026-09-25T09:55:00Z",
                        "odds_1x2": [2, 3.5, 4],
                    }
                ],
            }
        ],
    }
    return {"fixtures": [fixture]}, snapshot


def test_devig_and_latest_quote_only_once_per_bookmaker():
    coupon, snapshot = market_case()
    older = copy.deepcopy(snapshot["fixtures"][0]["quotes"][0])
    older.update(observed_at="2026-09-25T09:00:00Z", odds_1x2=[1.2, 8, 9])
    snapshot["fixtures"][0]["quotes"].append(older)
    result = compare_snapshot(coupon, snapshot, "2026-09-25T11:00:00Z")
    assert result["fixtures"][0]["bookmaker_count"] == 1
    np.testing.assert_allclose(result["fixtures"][0]["market_1x2"], devig([2, 3.5, 4])[0])


@pytest.mark.parametrize("odds", [[1, 2, 3], [0, 2, 3], [float("nan"), 2, 3], [2, 3]])
def test_bad_odds_rejected(odds):
    with pytest.raises(ValueError):
        devig(odds)


def test_unknown_timezone_future_snapshot_and_inplay_rejected():
    with pytest.raises(ValueError):
        instant("2026-09-25T12:00:00")
    coupon, snapshot = market_case()
    with pytest.raises(ValueError):
        compare_snapshot(coupon, snapshot, "2026-09-25T09:59:00Z")
    with pytest.raises(ValueError):
        compare_snapshot(coupon, snapshot, "2026-09-27T17:00:00Z")


@pytest.mark.parametrize("observed", ["2026-09-25T10:05:00Z", "2026-09-20T10:00:00Z"])
def test_future_and_stale_quotes_are_not_used(observed):
    coupon, snapshot = market_case()
    snapshot["fixtures"][0]["quotes"][0]["observed_at"] = observed
    result = compare_snapshot(coupon, snapshot, "2026-09-25T11:00:00Z")
    assert result["matched_fixtures"] == 0
    assert len(result["missing"]) == 1


def test_late_archive_retrieval_is_explicit_and_crowd_is_separate():
    coupon, snapshot = market_case()
    snapshot["retrieved_at"] = "2026-09-28T12:00:00Z"
    snapshot["fixtures"][0]["crowd"] = {
        "observed_at": "2026-09-25T09:00:00Z",
        "source_url": "https://example.org/crowd",
        "shares_1x2": [0.8, 0.1, 0.1],
    }
    result = compare_snapshot(coupon, snapshot, "2026-09-25T11:00:00Z")
    assert not result["available_to_this_app_before_decision"]
    assert result["fixtures"][0]["crowd_shares_1x2"] == [0.8, 0.1, 0.1]
    assert result["fixtures"][0]["market_1x2"] != [0.8, 0.1, 0.1]


def registry_case():
    now = datetime.now(UTC)
    kickoff = (now + timedelta(days=5)).replace(hour=12, minute=0, second=0, microsecond=0)
    fixtures = [
        {
            "position": i + 1,
            "home_team": f"H{i}",
            "away_team": f"A{i}",
            "competition_code": "es.1",
            "starts_at": kickoff.isoformat(),
        }
        for i in range(15)
    ]
    predictions = [
        {**f, "date": kickoff.date().isoformat(), "p_home": 0.5, "p_draw": 0.3, "p_away": 0.2}
        for f in fixtures
    ]
    strategy = {"cost_eur": 1.5, "columns": [{"signs": ["1"] * 14}, {"signs": ["X"] * 14}]}
    report = {
        "created_at": now.isoformat(),
        "inputs": {"data": "a" * 64},
        "source_sha256": {"code": "b" * 64},
        "coupons": [
            {
                "fixtures": predictions[:14],
                "pleno": {**predictions[14], "prediction": "1-0"},
                "cutoff": now.date().isoformat(),
                "model": {"training_last_date": (now - timedelta(days=1)).date().isoformat()},
                "budgets": {"5.00": {"budget_eur": 5, "strategies": {"full_system": strategy}}},
            }
        ],
    }
    manifest = {
        "schema_version": 1,
        "contest_id": "sample",
        "source_url": "https://example.org/contest",
        "captured_at": now.isoformat(),
        "closes_at": (kickoff - timedelta(hours=1)).isoformat(),
        "contest_date": kickoff.date().isoformat(),
        "primary_strategy": "full_system",
        "fixtures": fixtures,
    }
    return now, report, manifest


def test_registration_writes_once_and_detects_modified_forecast(tmp_path):
    _, report, manifest = registry_case()
    forecast, official = tmp_path / "input.json", tmp_path / "official.json"
    forecast.write_text(json.dumps(report), encoding="utf-8")
    official.write_text(json.dumps(manifest), encoding="utf-8")
    root = tmp_path / "registry"
    seal = register_forecast(forecast, official, root)
    assert seal["paper_only"] and not seal["official_inputs_independently_verified"]
    assert verify_record(root / "sample")["contest_id"] == "sample"
    with pytest.raises(FileExistsError):
        register_forecast(forecast, official, root)
    (root / "sample/forecast.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        verify_record(root / "sample")


@pytest.mark.parametrize(
    "problem", ["late", "future_manifest", "wrong_team", "overspend", "example", "future_training"]
)
def test_registration_rejects_invalid_or_late_records(problem):
    now, report, manifest = registry_case()
    if problem == "late":
        manifest["closes_at"] = now.isoformat()
    elif problem == "future_manifest":
        manifest["captured_at"] = (now + timedelta(hours=1)).isoformat()
    elif problem == "wrong_team":
        manifest["fixtures"][0]["home_team"] = "Other"
    elif problem == "overspend":
        report["coupons"][0]["budgets"]["5.00"]["strategies"]["full_system"]["cost_eur"] = 10
    elif problem == "example":
        manifest["is_example"] = True
    else:
        report["coupons"][0]["model"]["training_last_date"] = now.date().isoformat()
    with pytest.raises(ValueError):
        validate_registration(report, manifest, now)


def test_registered_portfolio_settles_once_with_official_signs(tmp_path, monkeypatch):
    from quantfootball.data.teams import canonicalize_team
    from quantfootball.quiniela import registry
    from quantfootball.quiniela.settlement import SELAE_ALIASES, parse_official_extract

    source = Path(__file__).parent / "fixtures/official_2025-05-25.txt"
    coupon = parse_official_extract(source.read_text(encoding="utf-8"), "2025-05-25")
    _, report, manifest = registry_case()
    now = datetime(2025, 5, 23, 10, tzinfo=UTC)
    manifest.update(
        captured_at=now.isoformat(), closes_at="2025-05-25T10:00:00Z", contest_date="2025-05-25"
    )
    report["created_at"] = now.isoformat()
    forecast = report["coupons"][0]
    forecast["cutoff"] = "2025-05-23"
    forecast["model"]["training_last_date"] = "2025-05-22"
    for i, row in enumerate([*coupon["fixtures"], coupon["pleno"]]):
        for side in ("home", "away"):
            name = canonicalize_team(SELAE_ALIASES.get(row[f"{side}_raw"], row[f"{side}_raw"]))
            manifest["fixtures"][i][f"{side}_team"] = name
            target = forecast["fixtures"][i] if i < 14 else forecast["pleno"]
            target[f"{side}_team"] = name
            target["date"] = "2025-05-25"
        manifest["fixtures"][i]["starts_at"] = "2025-05-25T16:00:00Z"
    signs = [f["sign"] for f in coupon["fixtures"]]
    other = signs.copy()
    other[0] = "X" if signs[0] != "X" else "1"
    strategy = forecast["budgets"]["5.00"]["strategies"]["full_system"]
    strategy["columns"] = [{"signs": signs}, {"signs": other}]
    forecast["pleno"]["prediction"] = "1-1"  # Actual is 0-M, so no Pleno payout.

    class FrozenClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(registry, "datetime", FrozenClock)
    input_file, manifest_file = tmp_path / "input.json", tmp_path / "official.json"
    input_file.write_text(json.dumps(report), encoding="utf-8")
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    root = tmp_path / "registered"
    register_forecast(input_file, manifest_file, root)
    assert registry_summary(root)["pending_count"] == 1
    monkeypatch.undo()
    receipt = settle_record(
        root / "sample", source, "https://www.loteriasyapuestas.es/es/la-quiniela/resultados"
    )
    expected = sum(float(coupon["prizes"][c]["unit_eur"]) for c in ("14", "13"))
    assert receipt["strategies"]["full_system"]["gross_return_eur"] == pytest.approx(expected)
    with pytest.raises(FileExistsError):
        settle_record(
            root / "sample", source, "https://www.loteriasyapuestas.es/es/la-quiniela/resultados"
        )
    summary = registry_summary(root)
    assert summary["settled_count"] == 1 and summary["pending_count"] == 0
    assert summary["settled_cost_eur"] == 1.5
    (root / "incomplete").mkdir()
    assert registry_summary(root)["invalid_count"] == 1
