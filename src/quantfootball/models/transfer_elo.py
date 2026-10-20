"""Elo on a common scale across divisions, with explicit season transition priors."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class TransferElo:
    league_gap: float = 200.0
    carryover: float = 0.75
    newcomer_penalty: float = 80.0
    home_advantage: float = 65.0
    k_factor: float = 20.0
    state: dict = field(default_factory=dict, init=False)
    counts: dict = field(default_factory=dict, init=False)
    first_season: str | None = field(default=None, init=False)

    def __post_init__(self):
        if (
            not np.isfinite([self.league_gap, self.carryover, self.newcomer_penalty]).all()
            or self.league_gap < 0
            or not 0 <= self.carryover <= 1
            or self.newcomer_penalty < 0
        ):
            raise ValueError("Invalid transfer parameters.")

    def center(self, code):
        if code not in ("es.1", "es.2"):
            raise ValueError("Unsupported division.")
        return 1500.0 - (self.league_gap if code == "es.2" else 0)

    def rating(self, team, code, season):
        center = self.center(code)
        if team not in self.state:
            return center - (
                self.newcomer_penalty if self.first_season and season != self.first_season else 0
            )
        previous = self.state[team]
        if previous["season"] == season:
            if previous["code"] != code:
                raise ValueError("Team appears in two regular divisions in the same season.")
            return previous["rating"]
        years = int(season[:4]) - int(previous["season"][:4])
        if years <= 0:
            raise ValueError("Cannot predict an earlier season from a later state.")
        # Shrink deviations toward the last observed league's center. Preserve the
        # global difference in level on promotion/relegation; decay longer absences.
        old_center = self.center(previous["code"])
        return old_center + self.carryover**years * (previous["rating"] - old_center)

    def predict_proba(self, home, away, code, season):
        if home == away:
            raise ValueError("A team cannot play itself.")
        h, a = self.rating(home, code, season), self.rating(away, code, season)
        total, draws = self.counts.get(code, (0.0, 0.0))
        draw_factor = 2 * (draws + 1) / (total - draws + 2)
        z = 10 ** ((h + self.home_advantage - a) / 400)
        tie = draw_factor * np.sqrt(z)
        return dict(
            zip(("H", "D", "A"), [z / (z + 1 + tie), tie / (z + 1 + tie), 1 / (z + 1 + tie)])
        )

    def update(self, home, away, code, season, result, weight=1.0):
        if result not in ("H", "D", "A") or not np.isfinite(weight) or weight <= 0:
            raise ValueError("Invalid outcome or update weight.")
        if self.first_season is None:
            self.first_season = season
        p = self.predict_proba(home, away, code, season)
        delta = (
            self.k_factor * weight * ({"H": 1, "D": 0.5, "A": 0}[result] - p["H"] - 0.5 * p["D"])
        )
        h, a = self.rating(home, code, season), self.rating(away, code, season)
        self.state[home] = {"rating": h + delta, "code": code, "season": season}
        self.state[away] = {"rating": a - delta, "code": code, "season": season}
        total, draws = self.counts.get(code, (0.0, 0.0))
        self.counts[code] = (total + weight, draws + weight * (result == "D"))

    def fit(self, history, cutoff, week_weights=None):
        boundary = pd.Timestamp(cutoff)
        if pd.isna(boundary) or boundary.tz is not None or boundary != boundary.normalize():
            raise ValueError("Cutoff must be a local calendar date.")
        data = history.copy()
        data["date"] = pd.to_datetime(data.date)
        data = data[data.date < boundary].sort_values(["date", "home_team"], kind="stable")
        if data.empty:
            raise ValueError("No training history before cutoff.")
        if "gender" in data and not data.gender.eq("men").all():
            raise ValueError("Only men's regular league data are supported.")
        self.state, self.counts, self.first_season = {}, {}, None
        for m in data.itertuples(index=False):
            week = m.date - pd.Timedelta(days=m.date.dayofweek)
            self.update(
                m.home_team,
                m.away_team,
                m.competition_code,
                m.season,
                m.result,
                1.0 if week_weights is None else week_weights[week],
            )
        return self
