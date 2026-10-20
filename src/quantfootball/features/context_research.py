"""Separate research features; frozen production feature versions stay unchanged."""

from collections import defaultdict, deque

import numpy as np
import pandas as pd


def context_table(history):
    """Only results strictly before the Monday cutoff enter a fixture's features.

    Schedule dates are final archived dates, not historically captured schedules.
    Calendar features cover league matches only, never pretend to include cups.
    """
    data = history.copy()
    if not data.competition_code.isin(["es.1", "es.2"]).all():
        raise ValueError("Research context currently supports men's Primera/Segunda only.")
    data["date"] = pd.to_datetime(data.date)
    if data.date.isna().any() or data.match_id.duplicated().any():
        raise ValueError("Unique matches with valid dates are required.")
    data = data.sort_values(["date", "match_id"])
    data["cutoff"] = data.date - pd.to_timedelta(data.date.dt.dayofweek, unit="D")
    records, state, cursor, rows = list(data.itertuples(index=False)), defaultdict(lambda: deque(maxlen=50)), 0, []
    for cutoff, block in data.groupby("cutoff", sort=True):
        while cursor < len(records) and records[cursor].date < cutoff:
            m = records[cursor]
            for team, gf, ga in [(m.home_team, m.home_goals, m.away_goals), (m.away_team, m.away_goals, m.home_goals)]:
                state[team].append((m.date, m.competition_code, float(gf), float(ga)))
            cursor += 1
        for fixture in block.itertuples(index=False):
            row = {"match_id": fixture.match_id}
            teams = []
            for team in (fixture.home_team, fixture.away_team):
                games = list(state[team])
                recent = games[-20:]
                # Fixed sensitivity, selected before evaluation; not a fitted league gap.
                factors = [1 if g[1] == fixture.competition_code else .8 if fixture.competition_code == "es.1" else 1.25 for g in recent]
                consecutive = 0
                for game in reversed(games):
                    if game[1] != fixture.competition_code:
                        break
                    consecutive += 1
                values = {
                    "transfer_games_current_division": min(consecutive, 20),
                    "transfer_previous_division_fraction": sum(g[1] != fixture.competition_code for g in recent) / max(1, len(recent)),
                    "transfer_scaled_gf": (sum(g[2] * f for g, f in zip(recent, factors)) + 6.25) / (len(recent) + 5),
                    "transfer_scaled_ga": (sum(g[3] / f for g, f in zip(recent, factors)) + 6.25) / (len(recent) + 5),
                    "calendar_league_rest_at_match": np.log1p(min(60, (fixture.date - games[-1][0]).days) if games else 60),
                    "calendar_league_games7_before_cutoff": sum(0 < (cutoff - g[0]).days <= 7 for g in games),
                    "calendar_league_games21_before_cutoff": sum(0 < (cutoff - g[0]).days <= 21 for g in games),
                }
                teams.append(values)
            for name in teams[0]:
                row["home_" + name] = teams[0][name]
                row["away_" + name] = teams[1][name]
                row["diff_" + name] = teams[0][name] - teams[1][name]
            rows.append(row)
    return pd.DataFrame(rows)
