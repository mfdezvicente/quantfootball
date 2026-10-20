"""Ablate transfer/calendar features; old holdouts are retrospective diagnostics only."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from quantfootball.evaluation.advanced import paired_week_bootstrap, summarize
from quantfootball.features.context_research import context_table
from quantfootball.features.form import create_feature_table
from quantfootball.models.form import FormClassifier

PROBS = ["p_home", "p_draw", "p_away"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--incumbent-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    history = pd.read_parquet(args.dataset)
    history = history[history.competition_code.isin(["es.1", "es.2"]) & (history.date < "2026-07-01")]
    base = create_feature_table(history, feature_version=2)
    extra = context_table(history)
    full = base.merge(extra, on="match_id", validate="one_to_one")
    experiment = {"created_at": datetime.now(UTC).isoformat(), "status": "retrospective_research_not_deployed",
                  "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
                  "selection_period": "2022-07-01 <= date < 2024-07-01", "diagnostic_period": "2024-07-01 <= date < 2026-07-01",
                  "method": "Fixed logistic C=0.1; train before 2022 for selection, refit before 2024 for diagnostics; no within-period refits",
                  "limitations": ["Diagnostic seasons were inspected in earlier research; not untouched confirmation",
                      "Final archived schedules, league-only calendar, no injuries/xG or historical publication-time guarantee",
                      "Different retraining cadence from incumbent; promotion requires new prospective evidence",
                      "Liga F excluded from this research, not pooled with men's teams"], "divisions": {}}
    for code in ("es.1", "es.2"):
        frames, ranking = {}, []
        for name, groups in [("base", []), ("transfer", ["transfer"]), ("calendar", ["calendar"]), ("both", ["transfer", "calendar"])]:
            keep = list(base.columns) + [c for c in extra if any("_" + group + "_" in c for group in groups)]
            frame = full.loc[full.competition_code.eq(code), keep].copy()
            frames[name] = frame
            model = FormClassifier({"kind": "logistic", "C": .1}).fit(frame, "2022-07-01")
            val = frame[(frame.date >= "2022-07-01") & (frame.date < "2024-07-01")].copy()
            val[PROBS] = model.predict_proba(val)
            ranking.append({"name": name, "metrics": summarize(val)})
        ranking.sort(key=lambda r: (r["metrics"]["log_loss"], r["name"] != "base", r["name"]))
        # Freeze selection before any diagnostic scores are computed.
        winner = ranking[0]["name"]
        (args.output_dir / f"{code}.selection.json").write_text(json.dumps(ranking, indent=2), encoding="utf-8")
        reference_path = args.incumbent_dir / f"{code}.selected.parquet"
        reference = pd.read_parquet(reference_path)
        diagnostics, selected_frames = {}, {}
        for name, frame in frames.items():
            model = FormClassifier({"kind": "logistic", "C": .1}).fit(frame, "2024-07-01")
            held = frame[(frame.date >= "2024-07-01") & (frame.date < "2026-07-01")].copy()
            held[PROBS] = model.predict_proba(held)
            # Every comparison uses identical fixture IDs; missing baseline rows fail loudly.
            matched = reference.set_index("match_id").reindex(held.match_id).reset_index()
            if matched[PROBS].isna().any().any():
                raise ValueError("Incumbent missing diagnostic fixture probabilities.")
            diagnostics[name] = {"metrics": summarize(held), "vs_incumbent": paired_week_bootstrap(held, matched)}
            selected_frames[name] = held
            held[["match_id", "date", "cutoff", "result", *PROBS]].to_parquet(args.output_dir / f"{code}.{name}.parquet", index=False)
        for name, held in selected_frames.items():
            diagnostics[name]["vs_same_classifier_base"] = paired_week_bootstrap(held, selected_frames["base"])
        experiment["divisions"][code] = {"validation_winner": winner, "validation": ranking,
            "diagnostics": diagnostics, "incumbent_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest()}
        print(code, winner, {k: round(v["metrics"]["log_loss"], 6) for k, v in diagnostics.items()}, flush=True)
    source_root = Path(__file__).resolve().parents[1]
    experiment["source_sha256"] = {str(p.relative_to(source_root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__), *sorted((source_root / "src/quantfootball").rglob("*.py"))]}
    (args.output_dir / "evaluation.json").write_text(json.dumps(experiment, indent=2, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
