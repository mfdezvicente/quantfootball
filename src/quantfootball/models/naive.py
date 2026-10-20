"""Naive probabilistic baseline for Quant Football match outcomes."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


OUTCOMES = ("H", "D", "A")


@dataclass(frozen=True)
class NaiveOutcomeModel:
    """Constant 1X2 probabilities estimated from historical match frequencies."""

    home_win_prob: float
    draw_prob: float
    away_win_prob: float

    @classmethod
    def fit(cls, matches: pd.DataFrame) -> "NaiveOutcomeModel":
        """Estimate league-wide outcome frequencies from completed historical matches."""
        if "result" not in matches.columns:
            raise ValueError("Input data must contain a 'result' column.")

        results = matches["result"].dropna()
        if results.empty:
            raise ValueError("Cannot fit the naive model without completed match results.")

        invalid = set(results.unique()).difference(OUTCOMES)
        if invalid:
            raise ValueError(f"Unexpected result labels: {sorted(invalid)}")

        frequencies = results.value_counts(normalize=True)
        return cls(
            home_win_prob=float(frequencies.get("H", 0.0)),
            draw_prob=float(frequencies.get("D", 0.0)),
            away_win_prob=float(frequencies.get("A", 0.0)),
        )

    def predict_proba(self) -> dict[str, float]:
        """Return constant probabilities for home win, draw and away win."""
        return {
            "H": self.home_win_prob,
            "D": self.draw_prob,
            "A": self.away_win_prob,
        }

    def predict_frame(self, matches: pd.DataFrame) -> pd.DataFrame:
        """Attach constant 1X2 probabilities to a fixture frame."""
        output = matches.copy()
        output["p_home"] = self.home_win_prob
        output["p_draw"] = self.draw_prob
        output["p_away"] = self.away_win_prob
        return output
