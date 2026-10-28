"""Check sporting-result chronology independently of the observed scheduled hour."""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "result_chronology_under_test", ROOT / "src/quantfootball/data/results.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ResultLookup = MODULE.ResultLookup


def lookup_case(kickoff="12:00", *, actual_date="2026-10-26", scheduled_date=None):
    fixture = {
        "competition_code": "es.1", "home_team": "Real Madrid",
        "away_team": "Sevilla", "date": scheduled_date or actual_date,
    }
    data = pd.DataFrame([{
        **fixture, "date": actual_date, "gender": "men", "result": "H",
        "home_goals": 1, "away_goals": 0, "kickoff_time": kickoff,
    }])
    return ResultLookup(data), fixture


@pytest.mark.parametrize("hour", [11, 15])
def test_exact_date_rejects_registration_at_or_after_actual_start(hour):
    lookup, fixture = lookup_case()
    # Madrid is UTC+1 on this date, so local 12:00 starts at 11:00 UTC.
    with pytest.raises(ValueError, match="frozen prediction"):
        lookup.find(fixture, datetime(2026, 10, 26, hour, tzinfo=UTC))


def test_exact_date_accepts_a_verified_same_day_pre_kickoff_registration():
    lookup, fixture = lookup_case()
    result = lookup.find(fixture, datetime(2026, 10, 26, 10, 59, tzinfo=UTC))
    assert result["result_match_method"] == "exact_date"
    assert result["target"] == 0


@pytest.mark.parametrize("missing", [None, "", "   ", float("nan"), pd.NA])
def test_unknown_hour_is_safe_only_on_a_strictly_later_madrid_day(missing):
    lookup, fixture = lookup_case(missing)
    assert lookup.find(fixture, datetime(2026, 10, 25, 22, 59, tzinfo=UTC))
    # 23:00 UTC on the previous UTC day is already midnight in Madrid.
    with pytest.raises(ValueError, match="verified local kickoff"):
        lookup.find(fixture, datetime(2026, 10, 25, 23, tzinfo=UTC))


def test_registration_on_a_later_day_is_rejected_even_without_time():
    lookup, fixture = lookup_case(None)
    with pytest.raises(ValueError, match="before the frozen"):
        lookup.find(fixture, datetime(2026, 10, 27, tzinfo=UTC))


def test_naive_registration_is_rejected():
    lookup, fixture = lookup_case()
    with pytest.raises(ValueError, match="explicit timezone"):
        lookup.find(fixture, datetime(2026, 10, 25, 10, tzinfo=UTC).replace(tzinfo=None))


@pytest.mark.parametrize("invalid", ["24:00", "not a time", "12:00+01:00"])
def test_invalid_or_timezone_bearing_archived_hour_is_rejected(invalid):
    lookup, fixture = lookup_case(invalid)
    with pytest.raises(ValueError, match="local time|local kickoff"):
        lookup.find(fixture, datetime(2026, 10, 25, tzinfo=UTC))


@pytest.mark.parametrize("actual_date", ["2026-03-29", "2026-10-25"])
def test_nonexistent_or_ambiguous_madrid_hour_requires_review(actual_date):
    lookup, fixture = lookup_case("02:30", actual_date=actual_date)
    with pytest.raises(ValueError, match="nonexistent or ambiguous"):
        lookup.find(fixture, datetime(2026, 3, 1, tzinfo=UTC))


def test_changed_date_still_requires_time_for_prior_day_registration():
    lookup, fixture = lookup_case(None, scheduled_date="2026-10-25")
    with pytest.raises(ValueError, match="changed-date"):
        lookup.find(fixture, datetime(2026, 10, 24, tzinfo=UTC))


def test_changed_date_accepts_verified_time_and_preserves_audit_method():
    lookup, fixture = lookup_case("12:00", scheduled_date="2026-10-25")
    result = lookup.find(fixture, datetime(2026, 10, 24, tzinfo=UTC))
    assert result["result_match_method"] == "unique_same_fixture_within_3_days"
    assert result["actual_date"] == "2026-10-26"


def test_without_registration_timestamp_historical_resolution_is_unchanged():
    lookup, fixture = lookup_case(None)
    assert lookup.find(fixture)["result_match_method"] == "exact_date"
    fixture["date"] = "2026-10-25"
    assert lookup.find(fixture)["result_match_method"] == "unique_same_fixture_within_3_days"
