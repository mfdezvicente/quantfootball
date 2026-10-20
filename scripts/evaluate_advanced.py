"""Tune on 2022-24, then report untouched 2024-26 performance of a weekly forecast policy."""

from __future__ import annotations

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
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/processed/matches.parquet")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory; no overwrite")
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("Choose a new output directory to preserve previous experiments.")
    data = pd.read_parquet(args.dataset)
    data = data.loc[data["result"].notna()].copy()
    args.output_dir.mkdir(parents=True)
    validation = weekly_predictions(data, "2022-07-01", "2024-07-01", CANDIDATES)
    config, ranking = select_configuration(validation, CANDIDATES)
    config["selected_before"] = "2024-07-01"
    config["selection_objective"] = "Mean match log loss on 2022-23 and 2023-24"
    config["validation_winner"] = ranking[0]
    config["dataset_sha256"] = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    (args.output_dir / "model_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    validation.to_parquet(args.output_dir / "validation_predictions.parquet", index=False)
    # Configuration is fixed before accessing the holdout's evaluation scores.
    candidate = {key: config[key] for key in ("half_life_days", "ridge", "lookback_days")}
    heldout = weekly_predictions(data, "2024-07-01", "2026-07-01", [candidate])
    selected = blended_frame(heldout, 0, config["dc_weight"], config["temperature"])
    elo_temperature = next(item["temperature"] for item in ranking if item["dc_weight"] == 0)
    calibrated_elo = blended_frame(heldout, 0, 0, elo_temperature)
    calibrated_elo["model"] = "elo_calibrated"
    # Standalone DC score metrics do not belong to an Elo-only baseline.
    calibrated_elo = calibrated_elo.drop(columns=["pleno_log_loss", "pleno_brier", "pleno_correct"])
    heldout = pd.concat([heldout, selected, calibrated_elo], ignore_index=True)
    heldout.to_parquet(args.output_dir / "holdout_predictions.parquet", index=False)
    metrics = {name: summarize(frame) for name, frame in heldout.groupby("model")}
    seasons = {season: {name: summarize(frame) for name, frame in block.groupby("model")}
               for season, block in heldout.groupby("season")}
    report = {
        "created_at_utc": datetime.now(UTC).isoformat(), "configuration": config,
        "validation_ranking": ranking, "holdout": metrics, "holdout_by_season": seasons,
        "selected_vs_elo": paired_week_bootstrap(selected, heldout.loc[heldout["model"] == "elo"]),
        "selected_vs_calibrated_elo": paired_week_bootstrap(selected, calibrated_elo),
        "elo_baseline_temperature": elo_temperature,
        "dataset_counts": data.groupby("season").size().to_dict(),
        "cold_start_holdout_matches": int(heldout.loc[heldout["model"] == "dc_0", "cold_start"].sum()),
        "policy": "Monday cutoff; all matches in that week use a frozen model fitted to earlier dates.",
        "limitations": ["Primera only", "2024-25 has ten absent outcomes",
                        "Weekly blocks are not official Quiniela coupons",
                        "No odds, public selections, prize returns or demonstrated profitable edge",
                        "Historical source revisions are not reconstructed point-in-time",
                        "Unseen teams in evaluation use a neutral prior and are counted"],
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in [Path(__file__), *sorted((ROOT / "src/quantfootball").rglob("*.py"))]},
    }
    (args.output_dir / "evaluation.json").write_text(json.dumps(report, indent=2, allow_nan=False),
                                                   encoding="utf-8")
    for name, score in metrics.items():
        print(f"{name}: n={score['matches']} log_loss={score['log_loss']:.6f} "
              f"brier={score['brier']:.6f} accuracy={score['accuracy']:.2%}")
    print(f"Saved to {args.output_dir}")


if __name__ == "__main__":
    main()
