"""Elo-Davidson model for probabilistic football match outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


OUTCOME_SCORE = {"H": 1.0, "D": 0.5, "A": 0.0}


@dataclass
class EloModel:
    """Dynamic team-strength model with Davidson draw probabilities.

    Ratings are updated after each completed match. Predictions are therefore
    always based on information available before the match being predicted.
    """

    initial_rating: float = 1500.0
    k_factor: float = 20.0
    home_advantage: float = 65.0
    scale: float = 400.0
    draw_factor: float = 0.70
    ratings: dict[str, float] = field(default_factory=dict)

    def get_rating(self, team: str) -> float:
        """Return a team's current rating, initializing unseen teams at the prior."""
        return self.ratings.setdefault(team, self.initial_rating)

    def predict_proba(self, home_team: str, away_team: str) -> dict[str, float]:
        """Return pre-match home/draw/away probabilities using Davidson probabilities."""
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        z = 10.0 ** ((home_rating + self.home_advantage - away_rating) / self.scale)
        draw_term = self.draw_factor * (z**0.5)
        denominator = z + 1.0 + draw_term

        return {
            "H": z / denominator,
            "D": draw_term / denominator,
            "A": 1.0 / denominator,
        }

    def expected_home_score(self, home_team: str, away_team: str) -> float:
        """Return Elo expected score, counting a draw as one half."""
        probabilities = self.predict_proba(home_team, away_team)
        return probabilities["H"] + 0.5 * probabilities["D"]

    def update(self, home_team: str, away_team: str, result: str) -> float:
        """Update ratings after a completed match and return the home rating change."""
        if result not in OUTCOME_SCORE:
            raise ValueError(f"Unexpected result label: {result!r}")

        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)
        expected = self.expected_home_score(home_team, away_team)
        actual = OUTCOME_SCORE[result]

        delta = self.k_factor * (actual - expected)
        self.ratings[home_team] = home_rating + delta
        self.ratings[away_team] = away_rating - delta
        return delta

    def fit(self, matches: pd.DataFrame, *, reset: bool = True) -> "EloModel":
        """Process historical matches in chronological order."""
        required = {"date", "home_team", "away_team", "result"}
        missing = required.difference(matches.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        if reset:
            self.ratings.clear()

        order_columns = ["date"]
        if "kickoff_time" in matches.columns:
            order_columns.append("kickoff_time")

        ordered = matches.sort_values(order_columns, kind="stable")

        for match in ordered.itertuples(index=False):
            result = getattr(match, "result")
            if pd.isna(result):
                continue
            self.update(
                getattr(match, "home_team"),
                getattr(match, "away_team"),
                str(result),
            )

        return self

    def walk_forward(self, matches: pd.DataFrame) -> pd.DataFrame:
        """Predict each match before updating ratings with that match's result."""
        required = {"date", "home_team", "away_team", "result"}
        missing = required.difference(matches.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        order_columns = ["date"]
        if "kickoff_time" in matches.columns:
            order_columns.append("kickoff_time")

        ordered = matches.sort_values(order_columns, kind="stable").copy()
        rows: list[dict[str, object]] = []

        for match in ordered.itertuples(index=False):
            home_team = getattr(match, "home_team")
            away_team = getattr(match, "away_team")
            result = getattr(match, "result")

            home_rating = self.get_rating(home_team)
            away_rating = self.get_rating(away_team)
            probabilities = self.predict_proba(home_team, away_team)

            rows.append(
                {
                    "date": getattr(match, "date"),
                    "home_team": home_team,
                    "away_team": away_team,
                    "result": result,
                    "home_rating_pre": home_rating,
                    "away_rating_pre": away_rating,
                    "p_home": probabilities["H"],
                    "p_draw": probabilities["D"],
                    "p_away": probabilities["A"],
                }
            )

            if not pd.isna(result):
                self.update(home_team, away_team, str(result))

        return pd.DataFrame(rows)

    @staticmethod
    def estimate_draw_factor(matches: pd.DataFrame) -> float:
        """Estimate Davidson draw factor from historical draw frequency.

        At equal strengths, P(draw) = nu / (2 + nu), hence
        nu = 2*d / (1-d), where d is the empirical draw rate.
        """
        if "result" not in matches.columns:
            raise ValueError("Input data must contain a 'result' column.")

        results = matches["result"].dropna()
        if results.empty:
            raise ValueError("Cannot estimate draw factor without completed matches.")

        draw_rate = float((results == "D").mean())
        if not 0.0 < draw_rate < 1.0:
            raise ValueError("Draw rate must lie strictly between 0 and 1.")

        return 2.0 * draw_rate / (1.0 - draw_rate)
