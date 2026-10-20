"""Penalized dynamic attack/defence states with a joint low-score likelihood.

Each team has a state in every month in which it played. Gaussian transition
penalties pool neighbouring states, allowing more change over longer gaps. This
is a MAP-style penalized estimator, not a full Bayesian posterior. The correction
rho(h,a) = kappa / ((1+lambda_h)*(1+lambda_a)) is a bounded Dixon-Coles-type
extension: it preserves Poisson marginals and is valid for every future pairing.
It is deliberately distinguished from the original constant-rho Dixon-Coles.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson, skellam


@dataclass
class DynamicGoalModel:
    drift_precision: float = 48.0
    initial_precision: float = 2.0
    level_precision: float = 0.2
    mean_reversion_days: float = 730.0
    half_life_days: float = 730.0
    lookback_days: int = 1461
    correction_precision: float = 2.0
    use_correction: bool = True
    teams: dict = field(default_factory=dict, init=False)
    parameters: np.ndarray | None = field(default=None, init=False)
    diagnostics: dict = field(default_factory=dict, init=False)
    _keys: list = field(default_factory=list, init=False, repr=False)
    _last_states: dict = field(default_factory=dict, init=False, repr=False)
    _cutoff: pd.Timestamp | None = field(default=None, init=False, repr=False)

    def fit(self, matches, cutoff, *, week_weights=None):
        positive = [self.drift_precision, self.initial_precision, self.level_precision,
                    self.mean_reversion_days, self.half_life_days, self.correction_precision]
        if not np.isfinite(positive).all() or min(positive) <= 0 or self.lookback_days < 1:
            raise ValueError("Dynamic-model precisions, timescales and lookback must be positive.")
        boundary = pd.Timestamp(cutoff)
        if pd.isna(boundary) or boundary.tz is not None or boundary != boundary.normalize():
            raise ValueError("Cutoff must be a timezone-free calendar date.")
        required = {"date", "home_team", "away_team", "home_goals", "away_goals"}
        if not required.issubset(matches):
            raise ValueError(f"Missing goal-model columns: {sorted(required - set(matches))}")
        data = matches.copy()
        data["date"] = pd.to_datetime(data.date, errors="raise")
        data = data[(data.date < boundary) &
                    (data.date >= boundary - pd.Timedelta(days=self.lookback_days))]
        if data.empty or data.date.isna().any():
            raise ValueError("Dynamic goal model needs valid prior results inside its lookback.")
        if "competition_code" in data and data.competition_code.nunique() != 1:
            raise ValueError("Dynamic strengths must be fitted separately by competition.")
        for column in ("home_team", "away_team"):
            if not data[column].map(lambda x: isinstance(x, str) and bool(x.strip())).all():
                raise ValueError("Team names must be nonempty strings.")
        if (data.home_team == data.away_team).any():
            raise ValueError("A team cannot play itself.")
        if data.duplicated(["date", "home_team", "away_team"]).any():
            raise ValueError("Duplicate training fixtures.")
        goals = data[["home_goals", "away_goals"]].to_numpy(dtype=float)
        if not np.isfinite(goals).all() or (goals < 0).any() or (goals != np.floor(goals)).any():
            raise ValueError("Goals must be finite nonnegative integers.")
        month = (data.date.dt.year * 12 + data.date.dt.month - 1).to_numpy()
        keys = sorted(set(zip(data.home_team, month)) | set(zip(data.away_team, month)))
        states = {key: i for i, key in enumerate(keys)}
        n = len(keys)
        home = np.array([states[k] for k in zip(data.home_team, month)])
        away = np.array([states[k] for k in zip(data.away_team, month)])
        first, previous, current, gap = [], [], [], []
        last_states = {}
        for i, (team, period) in enumerate(keys):
            if team in last_states:
                j = last_states[team]
                previous.append(j)
                current.append(i)
                gap.append(period - keys[j][1])
            else:
                first.append(i)
            last_states[team] = i
        previous, current, first = [np.array(v, dtype=int) for v in (previous, current, first)]
        gap = np.array(gap, dtype=float)
        transition = self.drift_precision / gap
        decay = np.exp2(-gap * 30.4375 / self.mean_reversion_days)
        weights = np.exp2(-(boundary - data.date).dt.total_seconds().to_numpy() /
                          (86400 * self.half_life_days))
        if week_weights is not None:
            weeks = data.date.dt.normalize() - pd.to_timedelta(data.date.dt.dayofweek, unit="D")
            multipliers = weeks.map(week_weights).to_numpy(dtype=float)
            if not np.isfinite(multipliers).all() or (multipliers <= 0).any():
                raise ValueError("Every training week requires a finite positive multiplier.")
            weights *= multipliers
        x, y = goals.T
        low00, low01 = (x == 0) & (y == 0), (x == 0) & (y == 1)
        low10, low11 = (x == 1) & (y == 0), (x == 1) & (y == 1)

        def objective(theta):
            attack, defence = theta[2:2+n], theta[2+n:2+2*n]
            eta_h = theta[0] + theta[1] + attack[home] + defence[away]
            eta_a = theta[0] + attack[away] + defence[home]
            lh, la = np.exp(eta_h), np.exp(eta_a)
            loss = np.sum(weights * (lh - x * eta_h + la - y * eta_a))
            eh, ea = weights * (lh - x), weights * (la - y)
            coefficient, dh, da = np.zeros(len(data)), np.zeros(len(data)), np.zeros(len(data))
            coefficient[low00] = -lh[low00] * la[low00]
            coefficient[low01], coefficient[low10], coefficient[low11] = lh[low01], la[low10], -1
            dh[low00 | low01] = coefficient[low00 | low01]
            da[low00 | low10] = coefficient[low00 | low10]
            denominator = (1 + lh) * (1 + la)
            c = coefficient / denominator
            ch = dh / denominator - c * lh / (1 + lh)
            ca = da / denominator - c * la / (1 + la)
            kappa = theta[-1]
            tau = 1 + kappa * c
            loss -= np.sum(weights * np.log(tau))
            eh -= weights * kappa * ch / tau
            ea -= weights * kappa * ca / tau
            gradient = np.concatenate((
                [np.sum(eh + ea), np.sum(eh)],
                np.bincount(home, eh, minlength=n) + np.bincount(away, ea, minlength=n),
                np.bincount(away, eh, minlength=n) + np.bincount(home, ea, minlength=n),
                [-np.sum(weights * c / tau) + self.correction_precision * kappa],
            ))
            loss += self.correction_precision * kappa**2 / 2
            for offset, vector in [(2, attack), (2+n, defence)]:
                grad = gradient[offset:offset+n]
                residual = vector[current] - decay * vector[previous]
                loss += (np.sum(transition * residual**2) +
                         self.initial_precision * np.sum(vector[first]**2) +
                         self.level_precision * np.sum(vector**2)) / 2
                grad += self.level_precision * vector
                grad[first] += self.initial_precision * vector[first]
                np.add.at(grad, current, transition * residual)
                np.add.at(grad, previous, -decay * transition * residual)
            return float(loss), gradient

        initial = np.zeros(3 + 2*n)
        initial[0] = np.log(max(np.average(y, weights=weights), 0.1))
        initial[1] = np.log(max(np.average(x, weights=weights), 0.1)) - initial[0]
        # Prior fits provide only an optimization start, never extra training labels.
        if self.parameters is not None and self._cutoff <= boundary:
            old = {key: i for i, key in enumerate(self._keys)}
            old_n = len(old)
            initial[:2], initial[-1] = self.parameters[:2], self.parameters[-1]
            for i, key in enumerate(keys):
                j = old.get(key, self._last_states.get(key[0]))
                if j is not None:
                    initial[2+i] = self.parameters[2+j]
                    initial[2+n+i] = self.parameters[2+old_n+j]
        bounds = [(-2, 2), (-1, 1)] + [(-2.5, 2.5)] * (2*n)
        bounds += [(-0.95, 0.95) if self.use_correction else (0, 0)]
        fitted = minimize(objective, initial, jac=True, method="L-BFGS-B", bounds=bounds,
                          options={"maxiter": 1800, "ftol": 1e-9, "gtol": 1e-5, "maxls": 40})
        if not fitted.success or not np.isfinite(fitted.x).all():
            raise RuntimeError(f"Dynamic goal fit failed: {fitted.message}")
        self.parameters, self._keys, self._last_states = fitted.x, keys, last_states
        self.teams = {team: i for i, team in enumerate(sorted(last_states))}
        self._cutoff = boundary
        self.diagnostics = {
            "model": "dynamic_monthly_poisson_bounded_low_score_joint_MAP",
            "training_matches": len(data), "weighted_matches": float(weights.sum()),
            "training_last_date": data.date.max().isoformat(), "cutoff": boundary.date().isoformat(),
            "team_month_states": n, "parameters": len(initial), "converged": bool(fitted.success),
            "iterations": int(fitted.nit), "kappa": float(fitted.x[-1]),
            "drift_precision": self.drift_precision, "half_life_days": self.half_life_days,
            "mean_reversion_days": self.mean_reversion_days,
            "correction": "pair-scaled rho; not the original constant-rho Dixon-Coles",
            "estimation": "Penalized joint likelihood; no posterior integration",
        }
        return self

    def _strength(self, team, allow_unknown):
        if self.parameters is None:
            raise ValueError("Fit the dynamic goal model before predicting.")
        i = self._last_states.get(team)
        if i is None:
            if not allow_unknown:
                raise ValueError("Team has no history inside the dynamic-model lookback.")
            return 0.0, 0.0
        forecast_month = self._cutoff.year * 12 + self._cutoff.month - 1
        decay = np.exp2(-(forecast_month - self._keys[i][1]) * 30.4375 /
                        self.mean_reversion_days)
        n = len(self._keys)
        return decay * self.parameters[2+i], decay * self.parameters[2+n+i]

    def expected_goals(self, home, away, *, allow_unknown=False):
        if home == away:
            raise ValueError("A team cannot play itself.")
        ah, dh = self._strength(home, allow_unknown)
        aa, da = self._strength(away, allow_unknown)
        return (float(np.exp(self.parameters[0] + self.parameters[1] + ah + da)),
                float(np.exp(self.parameters[0] + aa + dh)))

    def predict_proba(self, home, away, *, allow_unknown=False, correction=True):
        lh, la = self.expected_goals(home, away, allow_unknown=allow_unknown)
        rho = self.parameters[-1] / ((1 + lh) * (1 + la)) if correction else 0
        shift = np.exp(-lh-la) * lh * la * rho
        values = np.array([skellam.sf(0, lh, la) + shift,
                           skellam.pmf(0, lh, la) - 2*shift,
                           skellam.cdf(-1, lh, la) + shift])
        if not np.isfinite(values).all() or values.min() < -1e-12:
            raise RuntimeError("Invalid dynamic-model probabilities.")
        values = np.maximum(values, 0)
        return dict(zip(("H", "D", "A"), (values / values.sum()).tolist()))

    def predict_pleno(self, home, away, *, allow_unknown=False):
        lh, la = self.expected_goals(home, away, allow_unknown=allow_unknown)
        ph = np.append(poisson.pmf(np.arange(3), lh), poisson.sf(2, lh))
        pa = np.append(poisson.pmf(np.arange(3), la), poisson.sf(2, la))
        grid = np.outer(ph, pa)
        shift = np.exp(-lh-la) * lh * la * self.parameters[-1] / ((1+lh)*(1+la))
        grid[:2, :2] += np.array([[-shift, shift], [shift, -shift]])
        labels = ("0", "1", "2", "M")
        if not np.isfinite(grid).all() or grid.min() < -1e-12:
            raise RuntimeError("Invalid dynamic-model Pleno distribution.")
        return {f"{h}-{a}": float(grid[i, j]) for i, h in enumerate(labels)
                for j, a in enumerate(labels)}

