"""Regularized linear and nonlinear probabilistic models of pre-match form features."""

import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from quantfootball.features.form import feature_columns

CANDIDATES = [
    {"kind": "logistic", "C": 0.01},
    {"kind": "logistic", "C": 0.1},
    {"kind": "logistic", "C": 1.0},
    {"kind": "boosting", "max_leaf_nodes": 7, "l2_regularization": 10.0},
    {"kind": "boosting", "max_leaf_nodes": 15, "l2_regularization": 10.0},
]

EXTENDED_CANDIDATES = [
    {"kind": "logistic", "C": 0.01},
    {"kind": "logistic", "C": 0.1},
    {"kind": "logistic", "C": 1.0},
    {"kind": "boosting", "max_leaf_nodes": 7, "l2_regularization": 30.0},
    {"kind": "neural", "hidden_layer_sizes": [12], "alpha": 30.0},
    {"kind": "neural", "hidden_layer_sizes": [24, 12], "alpha": 100.0},
]


class FormClassifier:
    def __init__(self, config, half_life_days=730):
        self.config = config
        self.half_life_days = half_life_days

    def fit(self, table, cutoff, week_weights=None):
        boundary = pd.Timestamp(cutoff)
        data = table[
            (table.date < boundary) & (table.date >= boundary - pd.Timedelta(days=6 * 365))
        ].copy()
        # Exclude first two seasons: initial team histories are sparse across the archive.
        data = data[data.date >= "2017-07-01"]
        if len(data) < 300 or set(data.result) != set("HDA"):
            raise ValueError("At least 300 prior examples and all three outcomes are required.")
        self.columns = feature_columns(data)
        weights = np.exp2(-(boundary - data.date).dt.days.to_numpy() / self.half_life_days)
        if week_weights is not None:
            weights *= data.cutoff.map(week_weights).to_numpy()
        weights /= weights.mean()
        if not np.isfinite(weights).all() or (weights <= 0).any():
            raise ValueError("Invalid historical sample weights.")
        settings = {k: v for k, v in self.config.items() if k != "kind"}
        if self.config["kind"] == "logistic":
            self.estimator = make_pipeline(
                StandardScaler(), LogisticRegression(**settings, max_iter=1000)
            )
            self.estimator.fit(
                data[self.columns], data.result, logisticregression__sample_weight=weights
            )
        elif self.config["kind"] == "boosting":
            self.estimator = HistGradientBoostingClassifier(
                **settings,
                learning_rate=0.05,
                max_iter=120,
                min_samples_leaf=40,
                early_stopping=False,
                random_state=20260925,
            )
            self.estimator.fit(data[self.columns], data.result, sample_weight=weights)
        elif self.config["kind"] == "neural":
            # Fixed architecture, epochs and seed. No random validation split
            # or future labels are used for early stopping.
            settings["hidden_layer_sizes"] = tuple(settings["hidden_layer_sizes"])
            maximum = settings.pop("max_iter", 250)
            max_fun = settings.pop("max_fun", 25000)
            self.estimator = make_pipeline(
                StandardScaler(),
                MLPClassifier(
                    **settings,
                    solver="lbfgs",
                    max_iter=maximum,
                    max_fun=max_fun,
                    early_stopping=False,
                    random_state=20261002,
                ),
            )
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always", ConvergenceWarning)
                self.estimator.fit(
                    data[self.columns], data.result, mlpclassifier__sample_weight=weights
                )
            self.fit_warnings = [
                str(w.message) for w in captured if issubclass(w.category, ConvergenceWarning)
            ]
        else:
            raise ValueError("Unknown form model.")
        self.training_last_date = data.date.max().isoformat()
        final = self.estimator[-1] if hasattr(self.estimator, "steps") else self.estimator
        self.iterations = int(np.asarray(getattr(final, "n_iter_", 0)).max())
        self.converged = not bool(getattr(self, "fit_warnings", []))
        return self

    def predict_proba(self, features):
        raw = self.estimator.predict_proba(features[self.columns])
        classes = list(self.estimator.classes_)
        probabilities = raw[:, [classes.index(label) for label in ("H", "D", "A")]]
        probabilities = np.clip(probabilities, 1e-12, 1)
        return probabilities / probabilities.sum(axis=1, keepdims=True)
