"""Chronological Liga F model selection with later diagnostic seasons."""

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
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", type=Path, default=ROOT / "data/processed/matches_ligaf.parquet")
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=False)
    data = pd.read_parquet(a.dataset)
    val = weekly_predictions(data, "2022-07-01", "2024-07-01", CANDIDATES)
    val.to_parquet(a.output_dir / "validation.parquet", index=False)
    settings, ranking = select_configuration(val, CANDIDATES)
    selected = ranking[0]
    diag = weekly_predictions(
        data,
        "2024-07-01",
        "2026-07-01",
        [{k: settings[k] for k in ("half_life_days", "ridge", "lookback_days")}],
    )
    output = blended_frame(diag, 0, settings["dc_weight"], settings["temperature"])
    output.to_parquet(a.output_dir / "selected.parquet", index=False)
    elo = diag[diag.model.eq("elo")].copy()
    metrics = {name: summarize(g) for name, g in diag.groupby("model")}
    metrics["selected"] = summarize(output)
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_sha256": hashlib.sha256(a.dataset.read_bytes()).hexdigest(),
        "selection_period": ["2022-07-01", "2024-07-01"],
        "diagnostic_period": ["2024-07-01", "2026-07-01"],
        "scope": "Women's models fit only women's prior results; strict weekly cutoffs",
        "leagues": {
            "es.w.1": {
                "configuration": settings,
                "validation_ranking": ranking,
                "metrics": metrics,
                "selected_vs_elo": paired_week_bootstrap(output, elo),
                "cold_start_matches": int(output.cold_start.sum()),
                "by_season": {s: summarize(g) for s, g in output.groupby("season")},
            }
        },
    }
    config = json.loads((ROOT / "configs/quiniela_spain.json").read_text(encoding="utf-8"))
    config["divisions"]["es.w.1"] = {
        **settings,
        "selected_before": "2024-07-01",
        "status": "experimental_women_extension",
        "gender": "women",
    }
    config["status"] = "mixed_competition_candidate_not_default"
    config["dataset_sha256"] = hashlib.sha256(
        (ROOT / "data/processed/matches_quiniela.parquet").read_bytes()
    ).hexdigest()
    for name, obj in [("evaluation.json", report), ("candidate_config.json", config)]:
        (a.output_dir / name).write_text(
            json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
        )
    print(
        "Selected",
        selected,
        "diagnostic",
        metrics["selected"],
        report["leagues"]["es.w.1"]["selected_vs_elo"],
    )


if __name__ == "__main__":
    main()
