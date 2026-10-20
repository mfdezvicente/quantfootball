"""Evaluate form-feature classifiers and validation-selected mixtures chronologically."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from quantfootball.evaluation.advanced import blended_frame, paired_week_bootstrap, summarize
from quantfootball.features.form import create_feature_table, feature_columns
from quantfootball.models.form import CANDIDATES, EXTENDED_CANDIDATES, FormClassifier

ROOT = Path(__file__).resolve().parents[1]
PROBS = ["p_home", "p_draw", "p_away"]


def mix(base, other, weight, temperature):
    probabilities = (1 - weight) * base + weight * other
    probabilities = probabilities ** (1 / temperature)
    return probabilities / probabilities.sum(axis=1, keepdims=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=ROOT / "outputs/reports/spain_v5")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--feature-version", type=int, choices=[1, 2], default=1)
    parser.add_argument("--extended", action="store_true")
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("Use a new output directory.")
    args.output_dir.mkdir(parents=True)
    dataset = ROOT / "data/processed/matches_spain.parquet"
    data = pd.read_parquet(dataset)
    baseline_config = json.loads((args.baseline / "model_config.json").read_text(encoding="utf-8"))
    dataset_hash = hashlib.sha256(dataset.read_bytes()).hexdigest()
    if dataset_hash != baseline_config["dataset_sha256"]:
        raise ValueError("Baseline predictions belong to a different dataset.")
    candidates = EXTENDED_CANDIDATES if args.extended else CANDIDATES
    table = create_feature_table(data, args.feature_version)
    table.to_parquet(args.output_dir / "features.parquet", index=False)
    targets = table[(table.date >= "2022-07-01") & (table.date < "2026-07-01")].copy()
    targets["fit_month"] = targets.cutoff.dt.to_period("M")
    predictions = []
    for number, settings in enumerate(candidates):
        parts = []
        for month, group in targets.groupby("fit_month", sort=True):
            cutoff = group.cutoff.min()
            model = FormClassifier(settings).fit(table, cutoff)
            output = group[
                ["match_id", "date", "cutoff", "season", "competition_code", "result"]
            ].copy()
            output[PROBS] = model.predict_proba(group)
            output["candidate"] = number
            output["coefficient_fit_cutoff"] = cutoff.isoformat()
            output["fit_iterations"] = model.iterations
            parts.append(output)
        candidate = pd.concat(parts, ignore_index=True)
        candidate.to_parquet(args.output_dir / f"candidate_{number}.parquet", index=False)
        predictions.append(candidate)
        print("Completed", number + 1, "/", len(candidates), settings, flush=True)
    all_predictions = pd.concat(predictions, ignore_index=True)
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_sha256": dataset_hash,
        "features": feature_columns(table),
        "feature_count": len(feature_columns(table)),
        "feature_version": args.feature_version,
        "feature_source": "Derived exclusively from the existing audited results and dates; no new third-party data",
        "training": "Six-year rolling window, two-year recency half-life; coefficients refit monthly using prior labels; features updated at weekly cutoffs",
        "validation": ["2022-07-01", "2024-07-01"],
        "diagnostic": ["2024-07-01", "2026-07-01"],
        "interpretation": "Previously inspected periods; exploratory retrospective evaluation, not an untouched holdout",
        "leagues": {},
    }
    deployment = json.loads(json.dumps(baseline_config))
    deployment.update(
        created_at=report["created_at"], status="experimental_form_candidate_not_default"
    )
    for code, settings in baseline_config["divisions"].items():
        val = pd.read_parquet(args.baseline / code / "validation.parquet")
        base_number = [(180, 2), (180, 10), (365, 2), (365, 10)].index(
            (settings["half_life_days"], settings["ridge"])
        )
        base = pd.concat(
            [
                blended_frame(val, base_number, settings["dc_weight"], settings["temperature"]),
                pd.read_parquet(args.baseline / code / "selected.parquet"),
            ]
        ).set_index("match_id")
        ranking = []
        for number, model_settings in enumerate(candidates):
            frame = all_predictions[
                (all_predictions.competition_code == code) & (all_predictions.candidate == number)
            ].set_index("match_id")
            validation = frame[frame.date < "2024-07-01"]
            b, t = base.loc[validation.index, PROBS].to_numpy(), validation[PROBS].to_numpy()
            targets_index = np.array([("H", "D", "A").index(s) for s in validation.result])
            for weight in (0, 0.25, 0.5, 0.75, 1):
                for temperature in (1.0,) if weight == 0 else (0.9, 1.0, 1.1):
                    p = mix(b, t, weight, temperature)
                    loss = float(-np.log(p[np.arange(len(p)), targets_index]).mean())
                    ranking.append(
                        {
                            "candidate": number,
                            "parameters": model_settings,
                            "weight": weight,
                            "temperature": temperature,
                            "log_loss": loss,
                        }
                    )
        ranking.sort(key=lambda r: (r["log_loss"], r["weight"], r["candidate"]))
        winner = ranking[0]
        frame = (
            all_predictions[
                (all_predictions.competition_code == code)
                & (all_predictions.candidate == winner["candidate"])
                & (all_predictions.date >= "2024-07-01")
            ]
            .set_index("match_id")
            .copy()
        )
        aligned = base.loc[frame.index].copy()
        frame[PROBS] = mix(
            aligned[PROBS].to_numpy(),
            frame[PROBS].to_numpy(),
            winner["weight"],
            winner["temperature"],
        )
        frame, aligned = frame.reset_index(), aligned.reset_index()
        frame.to_parquet(args.output_dir / f"{code}.selected.parquet", index=False)
        report["leagues"][code] = {
            "selected": winner,
            "validation_ranking": ranking,
            "metrics": summarize(frame),
            "baseline_metrics": summarize(aligned),
            "vs_baseline": paired_week_bootstrap(frame, aligned),
            "by_season": {season: summarize(g) for season, g in frame.groupby("season")},
            "standalone_candidates": {
                str(n): summarize(g)
                for n, g in all_predictions[
                    (all_predictions.competition_code == code)
                    & (all_predictions.date >= "2024-07-01")
                ].groupby("candidate")
            },
        }
        deployment["divisions"][code].update(
            form_weight=winner["weight"],
            form_temperature=winner["temperature"],
            form_parameters=winner["parameters"],
            form_feature_version=args.feature_version,
        )
        print(
            code,
            winner,
            "metrics",
            report["leagues"][code]["metrics"]["log_loss"],
            report["leagues"][code]["vs_baseline"],
            flush=True,
        )
    report["source_sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [
            Path(__file__),
            ROOT / "src/quantfootball/features/form.py",
            ROOT / "src/quantfootball/models/form.py",
        ]
    }
    for name, payload in [("evaluation.json", report), ("candidate_config.json", deployment)]:
        with (args.output_dir / name).open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)


if __name__ == "__main__":
    main()
