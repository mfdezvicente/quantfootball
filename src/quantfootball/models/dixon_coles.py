"""Time-decayed, regularized Poisson strengths with a Dixon-Coles correction.

Two-stage estimation: penalized Poisson likelihood, then a bounded low-score
correction. This is not the joint maximum-likelihood estimator of the 1997 paper.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from scipy.stats import poisson, skellam


@dataclass
class DixonColesModel:
    half_life_days: float = 365.0
    ridge: float = 5.0
    lookback_days: int = 1461
    teams: dict[str, int] = field(default_factory=dict, init=False)
    parameters: np.ndarray | None = field(default=None, init=False)
    rho: float = field(default=0.0, init=False)
    diagnostics: dict = field(default_factory=dict, init=False)

    def fit(self, matches: pd.DataFrame, cutoff: str | pd.Timestamp, *,
            week_weights: dict | None = None) -> DixonColesModel:
        if not np.isfinite(self.half_life_days) or self.half_life_days <= 0:
            raise ValueError("Half-life must be positive and finite.")
        if not np.isfinite(self.ridge) or self.ridge <= 0 or self.lookback_days < 1:
            raise ValueError("Ridge and lookback must be positive.")
        boundary = pd.Timestamp(cutoff)
        if pd.isna(boundary) or boundary.tz is not None or boundary != boundary.normalize():
            raise ValueError("Cutoff must be a timezone-free calendar date.")
        required = {"date", "home_team", "away_team", "home_goals", "away_goals"}
        if not required.issubset(matches.columns):
            raise ValueError(f"Missing goal-model columns: {sorted(required - set(matches.columns))}")
        data = matches.copy()
        data["date"] = pd.to_datetime(data["date"], errors="raise")
        data = data.loc[(data["date"] < boundary) & (
            data["date"] >= boundary - pd.Timedelta(days=self.lookback_days)
        )].copy()
        if data.empty:
            raise ValueError("No historical matches before cutoff inside lookback.")
        for name in ("home_team", "away_team"):
            if not data[name].map(lambda x: isinstance(x, str) and bool(x.strip())).all():
                raise ValueError("Historical team names must be nonempty strings.")
        if (data["home_team"] == data["away_team"]).any():
            raise ValueError("A team cannot play itself.")
        goals = data[["home_goals", "away_goals"]].to_numpy(dtype=float)
        if not np.isfinite(goals).all() or (goals < 0).any() or (goals != np.floor(goals)).any():
            raise ValueError("Training goals must be finite nonnegative integers.")
        if data.duplicated(["date", "home_team", "away_team"]).any():
            raise ValueError("Duplicate training fixtures.")
        names = sorted(set(data["home_team"]) | set(data["away_team"]))
        teams = {team: i for i, team in enumerate(names)}
        n = len(teams)
        home = data["home_team"].map(teams).to_numpy()
        away = data["away_team"].map(teams).to_numpy()
        x, y = goals.T
        age = (boundary - data["date"]).dt.total_seconds().to_numpy() / 86400
        weights = np.exp2(-age / self.half_life_days)
        if week_weights is not None:
            weeks = data['date'] - pd.to_timedelta(data['date'].dt.dayofweek, unit='D')
            multipliers = weeks.map(week_weights).to_numpy(dtype=float)
            if not np.isfinite(multipliers).all() or (multipliers <= 0).any():
                raise ValueError('Every training week requires a finite positive weight.')
            weights *= multipliers

        def objective(theta):
            base, advantage = theta[:2]
            attack, defence = theta[2:2 + n], theta[2 + n:]
            eta_home = base + advantage + attack[home] + defence[away]
            eta_away = base + attack[away] + defence[home]
            lh, la = np.exp(eta_home), np.exp(eta_away)
            loss = np.sum(weights * (lh - x * eta_home + la - y * eta_away))
            loss += self.ridge * np.sum(theta[2:] ** 2) / 2
            eh, ea = weights * (lh - x), weights * (la - y)
            gradient = np.concatenate((
                [np.sum(eh + ea), np.sum(eh)],
                np.bincount(home, eh, minlength=n) + np.bincount(away, ea, minlength=n),
                np.bincount(away, eh, minlength=n) + np.bincount(home, ea, minlength=n),
            ))
            gradient[2:] += self.ridge * theta[2:]
            return float(loss), gradient

        initial = np.zeros(2 + 2 * n)
        initial[0] = np.log(max(np.average(y, weights=weights), 0.1))
        initial[1] = np.log(max(np.average(x, weights=weights), 0.1)) - initial[0]
        result = minimize(objective, initial, jac=True, method="L-BFGS-B",
                          bounds=[(-2, 2), (-1, 1)] + [(-2, 2)] * (2 * n),
                          options={"maxiter": 500, "ftol": 1e-10})
        if not result.success or not np.isfinite(result.x).all():
            raise RuntimeError(f"Goal-model fit failed: {result.message}")
        theta = result.x
        attack, defence = theta[2:2 + n], theta[2 + n:]
        lh = np.exp(theta[0] + theta[1] + attack[home] + defence[away])
        la = np.exp(theta[0] + attack[away] + defence[home])
        # Bounds valid for every known pairing AND the zero-strength unseen-team prior.
        a, d = np.append(attack, 0), np.append(defence, 0)
        all_home = np.exp(theta[0] + theta[1] + a[:, None] + d[None, :])
        all_away = np.exp(theta[0] + a[None, :] + d[:, None])
        lower = max(-0.3, -1 / all_home.max(), -1 / all_away.max()) + 1e-9
        upper = min(0.3, 1 / (all_home * all_away).max()) - 1e-9
        coefficient = np.zeros(len(data))
        coefficient[(x == 0) & (y == 0)] = -(lh * la)[(x == 0) & (y == 0)]
        coefficient[(x == 0) & (y == 1)] = lh[(x == 0) & (y == 1)]
        coefficient[(x == 1) & (y == 0)] = la[(x == 1) & (y == 0)]
        coefficient[(x == 1) & (y == 1)] = -1
        correction = minimize_scalar(
            lambda rho: -np.sum(weights * np.log1p(coefficient * rho)),
            bounds=(lower, upper), method="bounded",
        )
        if not correction.success:
            raise RuntimeError("Low-score correction fit failed.")
        self.teams, self.parameters, self.rho = teams, theta, float(correction.x)
        self.diagnostics = {
            "training_matches": len(data), "weighted_matches": float(weights.sum()),
            "training_last_date": data["date"].max().isoformat(),
            "cutoff": boundary.date().isoformat(), "rho": self.rho,
            "rho_bounds": [float(lower), float(upper)],
            "converged": bool(result.success), "iterations": int(result.nit),
            "half_life_days": self.half_life_days, "ridge": self.ridge,
            "lookback_days": self.lookback_days,
        }
        return self

    def expected_goals(self, home: str, away: str, *, allow_unknown: bool = False) -> tuple:
        if self.parameters is None:
            raise ValueError("Fit the goal model before predicting.")
        if home == away:
            raise ValueError("A team cannot play itself.")
        if not allow_unknown and (home not in self.teams or away not in self.teams):
            raise ValueError("Team has no history inside the model's lookback window.")
        n = len(self.teams)
        theta = self.parameters

        def strength(team):
            i = self.teams.get(team)
            return (0.0, 0.0) if i is None else (theta[2 + i], theta[2 + n + i])

        ah, dh = strength(home)
        aa, da = strength(away)
        return float(np.exp(theta[0] + theta[1] + ah + da)), float(np.exp(theta[0] + aa + dh))

    def predict_proba(self, home: str, away: str, *, allow_unknown: bool = False,
                      correction: bool = True) -> dict[str, float]:
        lh, la = self.expected_goals(home, away, allow_unknown=allow_unknown)
        shift = np.exp(-lh - la) * lh * la * (self.rho if correction else 0)
        values = np.array([skellam.sf(0, lh, la) + shift,
                           skellam.pmf(0, lh, la) - 2 * shift,
                           skellam.cdf(-1, lh, la) + shift])
        if not np.isfinite(values).all() or values.min() < -1e-12:
            raise RuntimeError("Invalid goal-model probabilities.")
        values = np.maximum(values, 0)
        return dict(zip(("H", "D", "A"), (values / values.sum()).tolist()))

    def predict_pleno(self, home: str, away: str, *, allow_unknown: bool = False) -> dict:
        """Exact 0/1/2/3+ categories, retaining the full Poisson tail in M."""
        lh, la = self.expected_goals(home, away, allow_unknown=allow_unknown)
        ph = np.append(poisson.pmf(np.arange(3), lh), poisson.sf(2, lh))
        pa = np.append(poisson.pmf(np.arange(3), la), poisson.sf(2, la))
        grid = np.outer(ph, pa)
        shift = np.exp(-lh - la) * lh * la * self.rho
        grid[:2, :2] += np.array([[-shift, shift], [shift, -shift]])
        if grid.min() < -1e-12 or not np.isfinite(grid).all():
            raise RuntimeError("Invalid Pleno distribution.")
        labels = ("0", "1", "2", "M")
        return {f"{h}-{a}": float(grid[i, j]) for i, h in enumerate(labels)
                for j, a in enumerate(labels)}


def blend_probabilities(dc: dict, elo: dict, weight: float = 1, temperature: float = 1) -> dict:
    """A fixed validation-selected linear pool followed by temperature scaling."""
    if not 0 <= weight <= 1 or not np.isfinite(temperature) or temperature <= 0:
        raise ValueError("Invalid ensemble weight or temperature.")
    values = np.array([weight * dc[s] + (1 - weight) * elo[s] for s in ("H", "D", "A")])
    logits = np.log(np.clip(values, 1e-15, 1)) / temperature
    values = np.exp(logits - logits.max())
    return dict(zip(("H", "D", "A"), (values / values.sum()).tolist()))
