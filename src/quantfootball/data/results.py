"""Resolve final sporting results while auditing small kickoff date changes."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from quantfootball.market.snapshots import key


def _check_registration_before_kickoff(result, registered_at, *, changed_date):
    """Reject post-start predictions, including changes within the same day."""
    if registered_at is None:
        return
    if (not isinstance(registered_at, datetime) or registered_at.tzinfo is None
            or registered_at.utcoffset() is None):
        raise ValueError("Registration timestamp requires an explicit timezone.")
    madrid = ZoneInfo("Europe/Madrid")
    actual_day = datetime.fromisoformat(result["actual_date"]).date()
    registered_day = registered_at.astimezone(madrid).date()
    if registered_day > actual_day:
        raise ValueError("Match started before the frozen prediction.")
    value = result.get("kickoff_time")
    if not isinstance(value, str) or not value.strip():
        if changed_date or registered_day == actual_day:
            raise ValueError("Same-day or changed-date result requires a verified local kickoff time.")
        # Prior Madrid dates establish chronology even when archived time is unknown.
        return
    try:
        local = datetime.fromisoformat(f"{result['actual_date']}T{value.strip()}")
    except ValueError as exc:
        raise ValueError("Result requires a valid local kickoff time.") from exc
    if local.tzinfo is not None:
        raise ValueError("Archived kickoff_time must be a timezone-free Madrid local time.")
    kickoff = local.replace(tzinfo=madrid)
    if (kickoff.astimezone(UTC).astimezone(madrid).replace(tzinfo=None) != local
            or kickoff.utcoffset() != local.replace(tzinfo=madrid, fold=1).utcoffset()):
        raise ValueError("Archived local kickoff is nonexistent or ambiguous in Madrid.")
    if registered_at >= kickoff:
        raise ValueError("Match started before or at the frozen prediction.")


class ResultLookup:
    """Exact calendar identity first; unique same-fixture fallback within three days."""

    def __init__(self, data):
        self.exact, self.by_teams = {}, {}
        for row in data.to_dict("records"):
            if pd.isna(row.get("result")):
                continue
            home, away = row["home_goals"], row["away_goals"]
            if pd.isna(home) or pd.isna(away) or min(home, away) < 0 or int(home) != home or int(away) != away:
                raise ValueError("Completed sporting results require nonnegative integer goals.")
            target = 0 if home > away else 1 if home == away else 2
            date = pd.Timestamp(row["date"]).date().isoformat()
            identity = (*key(row), date)
            if row["result"] != ("H", "D", "A")[target] or identity in self.exact:
                raise ValueError("Repeated or inconsistent sporting result.")
            value = {**row, "actual_date": date, "target": target}
            self.exact[identity] = value
            self.by_teams.setdefault(key(row), []).append(value)

    def find(self, fixture, registered_at=None):
        scheduled = fixture["date"][:10]
        identity = key(fixture)
        exact = self.exact.get((*identity, scheduled))
        if exact is not None:
            _check_registration_before_kickoff(exact, registered_at, changed_date=False)
            return {**exact, "result_match_method": "exact_date"}
        candidates = [row for row in self.by_teams.get(identity, [])
                      if abs((pd.Timestamp(row["actual_date"]) - pd.Timestamp(scheduled)).days) <= 3]
        if len(candidates) > 1:
            raise ValueError("Ambiguous result after a fixture date change; review manually.")
        if not candidates:
            return None
        result = candidates[0]
        _check_registration_before_kickoff(result, registered_at, changed_date=True)
        return {**result, "result_match_method": "unique_same_fixture_within_3_days"}
