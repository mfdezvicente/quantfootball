"""Stable neural retry with fixed settings and explicit convergence diagnostics."""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from quantfootball.evaluation.advanced import summarize
from quantfootball.models.form import FormClassifier

ROOT = Path(__file__).resolve().parents[1]
PROBS = ["p_home", "p_draw", "p_away"]
CANDIDATES = [
    {
        "kind": "neural",
        "hidden_layer_sizes": [12],
        "alpha": 30.0,
        "activation": "tanh",
        "max_iter": 1500,
        "max_fun": 100000,
        "tol": 1e-4,
    },
    {
        "kind": "neural",
        "hidden_layer_sizes": [24, 12],
        "alpha": 100.0,
        "activation": "tanh",
        "max_iter": 1500,
        "max_fun": 100000,
        "tol": 1e-4,
    },
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--features", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=False)
    table = pd.read_parquet(a.features)
    targets = table[(table.date >= "2022-07-01") & (table.date < "2026-07-01")].copy()
    targets["fit_month"] = targets.cutoff.dt.to_period("M")
    report = {
        "features_sha256": hashlib.sha256(a.features.read_bytes()).hexdigest(),
        "candidates": [],
    }
    for n, settings in enumerate(CANDIDATES):
        parts, fits = [], []
        for _, group in targets.groupby("fit_month", sort=True):
            cutoff = group.cutoff.min()
            model = FormClassifier(settings).fit(table, cutoff)
            frame = group[
                ["match_id", "date", "cutoff", "season", "competition_code", "result"]
            ].copy()
            frame[PROBS] = model.predict_proba(group)
            parts.append(frame)
            fits.append(
                {
                    "cutoff": cutoff.isoformat(),
                    "iterations": model.iterations,
                    "converged": model.converged,
                    "warnings": model.fit_warnings,
                }
            )
        predictions = pd.concat(parts, ignore_index=True)
        predictions.to_parquet(a.output_dir / f"candidate_{n}.parquet", index=False)
        summary = {
            "parameters": settings,
            "fits": fits,
            "validation": {
                c: summarize(g)
                for c, g in predictions[predictions.date < "2024-07-01"].groupby("competition_code")
            },
            "diagnostic": {
                c: summarize(g)
                for c, g in predictions[predictions.date >= "2024-07-01"].groupby(
                    "competition_code"
                )
            },
        }
        report["candidates"].append(summary)
        print(
            n,
            "converged",
            sum(f["converged"] for f in fits),
            "/",
            len(fits),
            {c: m["log_loss"] for c, m in summary["diagnostic"].items()},
            flush=True,
        )
    report["source_sha256"] = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [Path(__file__), ROOT / "src/quantfootball/models/form.py"]
    }
    (a.output_dir / "evaluation.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
