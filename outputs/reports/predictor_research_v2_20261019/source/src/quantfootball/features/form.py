"""Rolling form and strength features frozen before the Monday of each match week."""

from collections import defaultdict, deque

import numpy as np
import pandas as pd

from quantfootball.models.transfer_elo import TransferElo


class FormHistory:
    def __init__(self, feature_version=1):
        if feature_version not in (1, 2):
            raise ValueError("Unsupported feature version.")
        self.feature_version = feature_version
        self.all = defaultdict(lambda: deque(maxlen=50))
        self.venue = defaultdict(lambda: deque(maxlen=20))
        self.strength = TransferElo(league_gap=200, carryover=0.75, newcomer_penalty=80)

    def update(self, match):
        code, season = match.competition_code, match.season
        home_rating = self.strength.rating(match.home_team, code, season)
        away_rating = self.strength.rating(match.away_team, code, season)
        for team, gf, ga, venue, opponent in [
            (match.home_team, match.home_goals, match.away_goals, "home", away_rating),
            (match.away_team, match.away_goals, match.home_goals, "away", home_rating),
        ]:
            record = {
                "date": match.date,
                "code": code,
                "gf": float(gf),
                "ga": float(ga),
                "points": 3.0 if gf > ga else 1.0 if gf == ga else 0.0,
                "draw": float(gf == ga),
                "opponent": opponent,
            }
            self.all[team].append(record)
            self.venue[(team, venue)].append(record)
        self.strength.update(match.home_team, match.away_team, code, season, match.result)

    def team_features(self, team, venue, code, season, cutoff):
        games = list(self.all[team])
        features = {}
        priors = {
            "gf": 1.25,
            "ga": 1.25,
            "points": 1.3,
            "draw": 0.28,
            "opponent": self.strength.center(code),
        }
        for window in (5, 20):
            chosen = games[-window:]
            for name, prior in priors.items():
                # Fixed pseudocount shrinkage limits extreme estimates for new clubs.
                features[f"{name}_{window}"] = (sum(g[name] for g in chosen) + 5 * prior) / (
                    len(chosen) + 5
                )
        played_here = list(self.venue[(team, venue)])
        for name in ("gf", "ga", "points"):
            features[f"venue_{name}"] = (sum(g[name] for g in played_here) + 5 * priors[name]) / (
                len(played_here) + 5
            )
        features["recent_count"] = len(games)
        features["rest_log_days"] = np.log1p(
            min((cutoff - games[-1]["date"]).days, 365) if games else 365
        )
        features["changed_division"] = float(bool(games) and games[-1]["code"] != code)
        features["strength"] = self.strength.rating(team, code, season)
        if self.feature_version == 2:
            # Every statistic comes from prior matches; date windows use the
            # common decision cutoff, never the eventual fixture kickoff.
            for window in (5, 20):
                chosen = games[-window:]
                for name in ("gf", "ga"):
                    features[f"{name}_variance_{window}"] = (
                        sum((g[name] - features[f"{name}_{window}"]) ** 2 for g in chosen)
                        + 5 * 1.25
                    ) / (len(chosen) + 5)
                for name, condition, prior in (
                    ("clean_sheet", lambda g: g["ga"] == 0, .28),
                    ("failed_score", lambda g: g["gf"] == 0, .28),
                    ("btts", lambda g: g["gf"] > 0 and g["ga"] > 0, .5),
                    ("over25", lambda g: g["gf"] + g["ga"] >= 3, .5),
                ):
                    features[f"{name}_{window}"] = (
                        sum(condition(g) for g in chosen) + 5 * prior
                    ) / (len(chosen) + 5)
            features["league_games_14d"] = sum(
                (cutoff - g["date"]).days <= 14 for g in games
            )
            features["league_games_30d"] = sum(
                (cutoff - g["date"]).days <= 30 for g in games
            )
            for name in ("gf", "ga", "points"):
                features[f"{name}_trend"] = features[f"{name}_5"] - features[f"{name}_20"]
                weights = [np.exp2(-(cutoff - g["date"]).days / 60) for g in games]
                features[f"{name}_decay60"] = (
                    sum(w * g[name] for w, g in zip(weights, games)) + 5 * priors[name]
                ) / (sum(weights) + 5)
        return features

    def features(self, home, away, code, season, cutoff):
        h = self.team_features(home, "home", code, season, cutoff)
        a = self.team_features(away, "away", code, season, cutoff)
        result = {f"home_{k}": v for k, v in h.items()}
        result.update({f"away_{k}": v for k, v in a.items()})
        result.update({f"diff_{k}": h[k] - a[k] for k in h})
        result["division_primera"] = float(code == "es.1")
        if self.feature_version == 2:
            # Goal-rate proxies, including venue and opponent defence effects.
            result["home_goal_proxy"] = np.sqrt(h["gf_20"] * a["ga_20"])
            result["away_goal_proxy"] = np.sqrt(a["gf_20"] * h["ga_20"])
            result["diff_goal_proxy"] = result["home_goal_proxy"] - result["away_goal_proxy"]
            result["diff_strength_squared"] = ((h["strength"] - a["strength"]) / 400) ** 2
        return result


def create_feature_table(history, feature_version=1):
    data = history.copy()
    data["date"] = pd.to_datetime(data.date)
    if data.date.isna().any() or not data.competition_code.isin(["es.1", "es.2"]).all():
        raise ValueError("Valid dated Primera/Segunda results are required.")
    if "gender" in data and not data.gender.eq("men").all():
        raise ValueError("Only the audited men's dataset is supported.")
    data = data.sort_values(["date", "home_team"], kind="stable")
    data["cutoff"] = data.date - pd.to_timedelta(data.date.dt.dayofweek, unit="D")
    state = FormHistory(feature_version)
    records = list(data.itertuples(index=False))
    cursor, rows = 0, []
    for cutoff, fixtures in data.groupby("cutoff", sort=True):
        while cursor < len(records) and records[cursor].date < cutoff:
            state.update(records[cursor])
            cursor += 1
        for fixture in fixtures.itertuples(index=False):
            features = state.features(
                fixture.home_team,
                fixture.away_team,
                fixture.competition_code,
                fixture.season,
                cutoff,
            )
            rows.append(
                {
                    "match_id": fixture.match_id,
                    "date": fixture.date,
                    "cutoff": cutoff,
                    "season": fixture.season,
                    "competition_code": fixture.competition_code,
                    "result": fixture.result,
                    **features,
                }
            )
    return pd.DataFrame(rows)


def forecast_features(history, fixtures, cutoff, feature_version=1):
    cutoff = pd.Timestamp(cutoff)
    if pd.isna(cutoff) or cutoff.tz is not None or cutoff != cutoff.normalize():
        raise ValueError("Use a calendar date as cutoff.")
    state = FormHistory(feature_version)
    data = history.copy()
    data["date"] = pd.to_datetime(data.date)
    data = data[data.date < cutoff].sort_values(["date", "home_team"], kind="stable")
    for row in data.itertuples(index=False):
        state.update(row)
    rows = []
    for fixture in fixtures.itertuples(index=False):
        date = pd.Timestamp(fixture.date)
        if date < cutoff:
            raise ValueError("Fixture is before the forecast cutoff.")
        year = date.year - (date.month < 7)
        rows.append(
            state.features(
                fixture.home_team,
                fixture.away_team,
                fixture.competition_code,
                f"{year}-{str(year + 1)[-2:]}",
                cutoff,
            )
        )
    return pd.DataFrame(rows)


def feature_columns(table):
    return [c for c in table if c.startswith(("home_", "away_", "diff_", "division_"))]
