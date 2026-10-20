"""Reproducible chronological diagnostics for each Spanish division."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from quantfootball.evaluation.advanced import (
    CANDIDATES,
    blended_frame,
    paired_week_bootstrap,
    select_configuration,
    summarize,
    weekly_predictions,
)

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "data/processed/matches_spain.parquet"
    )
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error(
            "Choose a new output directory; never reuse cached predictions across code or data revisions."
        )
    args.output_dir.mkdir(parents=True)
    data = pd.read_parquet(args.dataset)
    digest = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_sha256": digest,
        "interpretation": "Retrospective temporal diagnostic; 2024-26 already inspected, not a fresh holdout",
        "selection_period": ["2022-07-01", "2024-07-01"],
        "evaluation_period": ["2024-07-01", "2026-07-01"],
        "leagues": {},
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__), *sorted((ROOT / "src/quantfootball").rglob("*.py"))]
        },
    }
    configurations = {
        "selected_before": "2024-07-01",
        "divisions": {},
        "dataset_sha256": digest,
        "created_at": report["created_at"],
        "selection_mode": "Retrospective fit using only results earlier than selected_before",
    }
    for code, matches in data.groupby("competition_code"):
        directory = args.output_dir / code
        directory.mkdir(exist_ok=True)
        val_path = directory / "validation.parquet"
        if val_path.exists():
            validation = pd.read_parquet(val_path)
        else:
            validation = weekly_predictions(matches, "2022-07-01", "2024-07-01", CANDIDATES)
            validation.to_parquet(val_path, index=False)
        config, ranking = select_configuration(validation, CANDIDATES)
        config.update(selected_before="2024-07-01", dataset_sha256=digest)
        configurations["divisions"][code] = config
        target_path = directory / "diagnostic.parquet"
        if target_path.exists():
            forecasts = pd.read_parquet(target_path)
        else:
            forecasts = weekly_predictions(
                matches,
                "2024-07-01",
                "2026-07-01",
                [{k: config[k] for k in ("half_life_days", "ridge", "lookback_days")}],
            )
            forecasts.to_parquet(target_path, index=False)
        selected = blended_frame(forecasts, 0, config["dc_weight"], config["temperature"])
        selected.to_parquet(directory / "selected.parquet", index=False)
        metrics = {name: summarize(g) for name, g in forecasts.groupby("model")}
        metrics["selected"] = summarize(selected)
        report["leagues"][code] = {
            "configuration": config,
            "metrics": metrics,
            "validation_ranking": ranking,
            "by_season": {s: summarize(g) for s, g in selected.groupby("season")},
            "selected_vs_elo": paired_week_bootstrap(selected, forecasts[forecasts.model == "elo"]),
            "cold_start_matches": int(selected.cold_start.sum()),
            "cold_start_metrics": summarize(selected[selected.cold_start == True])
            if selected.cold_start.any()
            else None,
        }
        print(
            code,
            config,
            {k: {m: v[m] for m in ("log_loss", "brier", "accuracy")} for k, v in metrics.items()},
            flush=True,
        )
        (args.output_dir / "evaluation.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        (args.output_dir / "model_config.json").write_text(
            json.dumps(configurations, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
