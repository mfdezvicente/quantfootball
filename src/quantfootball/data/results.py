"""Resolve final sporting results while auditing small kickoff date changes."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from quantfootball.market.snapshots import key


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
            return {**exact, "result_match_method": "exact_date"}
        candidates = [row for row in self.by_teams.get(identity, [])
                      if abs((pd.Timestamp(row["actual_date"]) - pd.Timestamp(scheduled)).days) <= 3]
        if len(candidates) > 1:
            raise ValueError("Ambiguous result after a fixture date change; review manually.")
        if not candidates:
            return None
        result = candidates[0]
        # A moved match must still have started after the original registration.
        if registered_at is not None:
            time = result.get("kickoff_time")
            if not isinstance(time, str):
                raise ValueError("Changed-date result requires a verified local kickoff time.")
            kickoff = datetime.fromisoformat(f"{result['actual_date']}T{time}").replace(tzinfo=ZoneInfo("Europe/Madrid"))
            if kickoff <= registered_at:
                raise ValueError("Rescheduled match started before the frozen prediction.")
        return {**result, "result_match_method": "unique_same_fixture_within_3_days"}
