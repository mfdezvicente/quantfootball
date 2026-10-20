"""Compare dynamic goal states and temporal calibration against the incumbent.

The first validation season fits calibrators, the second ranks all alternatives.
Both seasons then fit the frozen final calibrator before the 2024-26 diagnostic.
Historical periods and incumbent settings have been inspected previously; this
is research, not a fresh untouched or fully nested model-selection holdout.
"""

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from quantfootball.evaluation.advanced import (
    blended_frame,
    paired_week_bootstrap,
    summarize,
)
from quantfootball.models.calibration import PROBS, calibrate_probabilities, fit_calibrator
from quantfootball.models.dynamic_goals import DynamicGoalModel

ROOT = Path(__file__).resolve().parents[1]
LABELS = ("H", "D", "A")
CANDIDATES = [
    {"drift_precision": precision, "initial_precision": 2.0, "level_precision": 0.2,
     "mean_reversion_days": 730.0, "half_life_days": 730.0, "lookback_days": 1461,
     "correction_precision": 2.0, "use_correction": True}
    for precision in (12.0, 48.0, 192.0)
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False),
                    encoding="utf-8")


def incumbent(archive, code):
    if code == "es.w.1":
        root = archive / "ligaf_v1"
        settings = json.loads((root / "candidate_config.json").read_text(encoding="utf-8"))
        settings = settings["divisions"][code]
        i = [(180, 2), (180, 10), (365, 2), (365, 10)].index(
            (settings["half_life_days"], settings["ridge"]))
        validation = blended_frame(pd.read_parquet(root / "validation.parquet"), i,
                                   settings["dc_weight"], settings["temperature"])
        return pd.concat([validation, pd.read_parquet(root / "selected.parquet")],
                         ignore_index=True)
    root = archive / "spain_v5"
    settings = json.loads((root / "model_config.json").read_text(encoding="utf-8"))["divisions"][code]
    i = [(180, 2), (180, 10), (365, 2), (365, 10)].index(
        (settings["half_life_days"], settings["ridge"]))
    base = pd.concat([
        blended_frame(pd.read_parquet(root / code / "validation.parquet"), i,
                      settings["dc_weight"], settings["temperature"]),
        pd.read_parquet(root / code / "selected.parquet"),
    ], ignore_index=True).set_index("match_id")
    selection = json.loads((archive / "research_selection_v1/evaluation.json").read_text(encoding="utf-8"))
    selected = selection["leagues"][code]["selected"]
    version, number = selected["candidate"].split("_")[1:]
    source = "form_v2_complete" if version == "v2" else "form_v1"
    frame = pd.read_parquet(archive / source / f"candidate_{number}.parquet")
    frame = frame[frame.competition_code.eq(code)].set_index("match_id")
    output = base.loc[frame.index].copy()
    mixed = (1-selected["weight"]) * output[PROBS].to_numpy() + selected["weight"] * frame[PROBS].to_numpy()
    mixed **= 1 / selected["temperature"]
    output[PROBS] = mixed / mixed.sum(axis=1, keepdims=True)
    return output.reset_index()


def generate(data, directory, code):
    targets = data[(data.date >= "2022-07-01") & (data.date < "2026-07-01")].copy()
    targets["cutoff"] = targets.date.dt.normalize() - pd.to_timedelta(targets.date.dt.dayofweek, unit="D")
    models = [DynamicGoalModel(**parameters) for parameters in CANDIDATES]
    rows, fits = [], []
    started = time.monotonic()
    for block, (cutoff, fixtures) in enumerate(targets.groupby("cutoff")):
        for i, model in enumerate(models):
            model.fit(data, cutoff)
            fits.append({"candidate": i, **model.diagnostics})
            for m in fixtures.itertuples(index=False):
                p = model.predict_proba(m.home_team, m.away_team, allow_unknown=True)
                lh, la = model.expected_goals(m.home_team, m.away_team, allow_unknown=True)
                scores = model.predict_pleno(m.home_team, m.away_team, allow_unknown=True)
                labels = ("0", "1", "2", "M")
                actual = f"{labels[min(int(m.home_goals), 3)]}-{labels[min(int(m.away_goals), 3)]}"
                rows.append({
                    "match_id": m.match_id, "season": m.season, "competition_code": code,
                    "date": m.date.isoformat(), "cutoff": cutoff.isoformat(), "result": m.result,
                    "model": f"dynamic_{i}", "candidate": i, "expected_home_goals": lh,
                    "expected_away_goals": la,
                    "cold_start": m.home_team not in model.teams or m.away_team not in model.teams,
                    "pleno_log_loss": float(-np.log(max(scores[actual], 1e-15))),
                    "pleno_brier": sum((p-(s == actual))**2 for s, p in scores.items()),
                    "pleno_correct": max(scores, key=scores.get) == actual,
                    **dict(zip(PROBS, [p[s] for s in LABELS])),
                })
        if block % 8 == 0:
            print(f"{code}: {cutoff.date()}, {block+1} weekly fits x 3; "
                  f"{time.monotonic()-started:.1f}s", flush=True)
        if block % 32 == 0:
            write_json(directory / "progress.json", {"code": code, "cutoff": cutoff.isoformat(),
                                                     "completed_weekly_blocks": block+1})
    pd.DataFrame(rows).to_parquet(directory / f"{code}.raw.parquet", index=False)
    write_json(directory / f"{code}.fits.json", fits)


def mixed_frame(base, dynamic, weight):
    output = base.copy()
    if weight:
        other = dynamic.set_index("match_id").reindex(base.match_id)
        if other[PROBS].isna().any().any() or not np.array_equal(other.result, base.result):
            raise ValueError("Dynamic and incumbent evaluation matches differ.")
        output[PROBS] = (1-weight) * base[PROBS].to_numpy() + weight * other[PROBS].to_numpy()
    # A calibrated/mixed 1X2 model does not inherit a score-grid evaluation.
    return output.drop(columns=[c for c in output if c.startswith("pleno_")])


def selection(archive, directory, config_path, dataset_hashes):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    report = {
        "created_at": datetime.now(UTC).isoformat(), "dataset_sha256": dataset_hashes,
        "calibration_fit_period": ["2022-07-01", "2023-07-01"],
        "ranking_period": ["2023-07-01", "2024-07-01"],
        "final_calibration_fit_period": ["2022-07-01", "2024-07-01"],
        "diagnostic_period": ["2024-07-01", "2026-07-01"], "candidates": CANDIDATES,
        "interpretation": "Inspected retrospective periods; incumbent hyperparameters were chosen on 2022-24, so this is not fully nested or a new untouched holdout.",
        "profitable_edge_demonstrated": False, "leagues": {},
        "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in [
            Path(__file__), ROOT / "src/quantfootball/models/dynamic_goals.py",
            ROOT / "src/quantfootball/models/calibration.py"]},
        "input_forecast_sha256": {},
        "generation_source_sha256": {p.name: digest(p) for p in sorted((directory / "source").glob("*.py"))},
    }
    for code in config["divisions"]:
        base = incumbent(archive, code).sort_values(["date", "match_id"]).reset_index(drop=True)
        raw_file = directory / f"{code}.raw.parquet"
        raw = pd.read_parquet(raw_file)
        report["input_forecast_sha256"][code] = digest(raw_file)
        base.to_parquet(directory / f"{code}.incumbent.parquet", index=False)
        report["input_forecast_sha256"][f"{code}.incumbent"] = digest(directory / f"{code}.incumbent.parquet")
        frames, ranking = {}, []
        for candidate, weight in [(-1, 0.0)] + [(i, w) for i in range(3) for w in (.25, .5, 1.0)]:
            frame = mixed_frame(base, raw[raw.candidate.eq(candidate)], weight)
            frames[(candidate, weight)] = frame
            for mode in ("identity", "temperature", "temperature_bias"):
                calibrated = fit_calibrator(frame, "2023-07-01", mode=mode, precision=50)
                val = frame[(frame.date >= "2023-07-01") & (frame.date < "2024-07-01")].copy()
                val[PROBS] = calibrate_probabilities(val[PROBS].to_numpy(), calibrated)
                metrics = summarize(val)
                ranking.append({"candidate": candidate, "dynamic_weight": weight,
                                "calibration_mode": mode, "validation_log_loss": metrics["log_loss"],
                                "validation_brier": metrics["brier"], "matches": len(val)})
        ranking.sort(key=lambda r: (r["validation_log_loss"], r["dynamic_weight"],
                                   r["calibration_mode"] != "identity"))
        winner = ranking[0]
        frame = frames[(winner["candidate"], winner["dynamic_weight"])]
        final_cal = fit_calibrator(frame, "2024-07-01", mode=winner["calibration_mode"], precision=50)
        output = frame[frame.date >= "2024-07-01"].copy()
        output[PROBS] = calibrate_probabilities(output[PROBS].to_numpy(), final_cal)
        output["model"] = "validation_selected_dynamic_calibration"
        output.to_parquet(directory / f"{code}.selected.parquet", index=False)
        original = base[base.date >= "2024-07-01"].copy()
        fits = json.loads((directory / f"{code}.fits.json").read_text(encoding="utf-8"))
        standalone = {str(i): summarize(raw[(raw.candidate == i) & (raw.date >= "2024-07-01")])
                      for i in range(3)}
        for metrics in standalone.values():
            metrics["pleno_categories"]["model"] = "Standalone dynamic score grid on historical matches, not official Pleno assignments"
        ablations = {}
        for name, source_frame, cal in [
            ("incumbent", base, {"mode": "identity"}),
            ("incumbent_calibration_only", base, fit_calibrator(base, "2024-07-01",
                 mode=winner["calibration_mode"], precision=50)),
            ("selected_pool_without_calibration", frame, {"mode": "identity"}),
            ("selected_pool_calibrated", frame, final_cal),
        ]:
            sub = source_frame[source_frame.date >= "2024-07-01"].copy()
            sub = sub.drop(columns=[c for c in sub if c.startswith("pleno_")])
            sub[PROBS] = calibrate_probabilities(sub[PROBS].to_numpy(), cal)
            ablations[name] = {"metrics": summarize(sub), "vs_incumbent": paired_week_bootstrap(sub, original)}
        report["leagues"][code] = {
            "selected": winner, "calibration": final_cal, "metrics": summarize(output),
            "incumbent_metrics": summarize(original), "vs_incumbent": paired_week_bootstrap(output, original),
            "validation_ranking": ranking, "standalone_dynamic_metrics": standalone,
            "ablations": ablations,
            "by_season": {season: summarize(g) for season, g in output.groupby("season")},
            "by_season_vs_incumbent": {season: paired_week_bootstrap(g, original[original.season.eq(season)])
                                      for season, g in output.groupby("season")},
            "convergence": {"fits": len(fits), "converged": sum(f["converged"] for f in fits),
                            "max_iterations": max(f["iterations"] for f in fits)},
            "cold_start_matches": int(raw[(raw.candidate == 0) & (raw.date >= "2024-07-01")].cold_start.sum()),
        }
        settings = config["divisions"][code]
        settings.update(dynamic_weight=winner["dynamic_weight"], calibration=final_cal)
        if winner["dynamic_weight"]:
            settings["dynamic_parameters"] = CANDIDATES[winner["candidate"]]
        print(code, winner, "diagnostic", report["leagues"][code]["metrics"]["log_loss"],
              "vs incumbent", report["leagues"][code]["vs_incumbent"], flush=True)
    config.update(status="experimental_dynamic_calibrated_candidate_not_default",
                  created_at=report["created_at"], research="dynamic_goals_temporal_calibration_v1")
    write_json(directory / "evaluation.json", report)
    write_json(directory / "candidate_config.json", config)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--men-dataset", type=Path, default=ROOT / "data/processed/matches_spain.parquet")
    p.add_argument("--women-dataset", type=Path, default=ROOT / "data/processed/matches_ligaf.parquet")
    p.add_argument("--archive-dir", type=Path, default=ROOT / "outputs/reports")
    p.add_argument("--incumbent-config", type=Path, default=ROOT / "configs/quiniela_mixed_candidate.json")
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--phase", choices=["all", "generate", "select"], default="all")
    a = p.parse_args()
    dataset_hashes = {"men": digest(a.men_dataset), "women": digest(a.women_dataset)}
    if a.phase in {"all", "generate"}:
        a.output_dir.mkdir(parents=True, exist_ok=False)
        source = a.output_dir / "source"
        source.mkdir()
        for file in [Path(__file__), ROOT / "src/quantfootball/models/dynamic_goals.py",
                     ROOT / "src/quantfootball/models/calibration.py"]:
            (source / file.name).write_bytes(file.read_bytes())
        write_json(a.output_dir / "manifest.json", {"dataset_sha256": dataset_hashes,
                                                   "candidates": CANDIDATES})
        data = pd.concat([pd.read_parquet(a.men_dataset), pd.read_parquet(a.women_dataset)],
                         ignore_index=True)
        data["date"] = pd.to_datetime(data.date)
        for code, matches in data.groupby("competition_code"):
            generate(matches, a.output_dir, code)
    if a.phase in {"all", "select"}:
        manifest = json.loads((a.output_dir / "manifest.json").read_text(encoding="utf-8"))
        if manifest["dataset_sha256"] != dataset_hashes or manifest["candidates"] != CANDIDATES:
            raise ValueError("Dataset or candidate definitions differ from the generated predictions.")
        selection(a.archive_dir, a.output_dir, a.incumbent_config, dataset_hashes)


if __name__ == "__main__":
    main()
