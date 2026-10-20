"""Choose across feature versions and converged neural retries using validation only."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from quantfootball.evaluation.advanced import blended_frame, paired_week_bootstrap, summarize

ROOT = Path(__file__).resolve().parents[1]
PROBS = ["p_home", "p_draw", "p_away"]


def mix(base, candidate, weight, temperature):
    p = ((1 - weight) * base + weight * candidate) ** (1 / temperature)
    return p / p.sum(axis=1, keepdims=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "form-v1", "form-v2", "neural"):
        p.add_argument(f"--{name}", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=False)
    base_config = json.loads((a.baseline / "model_config.json").read_text(encoding="utf-8"))
    sources, candidates = {}, []
    for version, root in [(1, a.form_v1), (2, a.form_v2)]:
        evaluation = json.loads((root / "evaluation.json").read_text(encoding="utf-8"))
        if evaluation["dataset_sha256"] != base_config["dataset_sha256"]:
            raise ValueError("Feature experiments use different match datasets.")
        settings = {
            r["candidate"]: r["parameters"]
            for r in evaluation["leagues"]["es.1"]["validation_ranking"]
        }
        for n, config in sorted(settings.items()):
            file = root / f"candidate_{n}.parquet"
            frame = pd.read_parquet(file)
            # The original neural runs hit their iteration limit; the fully
            # converged retries are considered below instead.
            if config["kind"] == "neural":
                continue
            identifier = f"form_v{version}_{n}"
            sources[identifier] = hashlib.sha256(file.read_bytes()).hexdigest()
            candidates.append((identifier, version, config, frame))
    neural = json.loads((a.neural / "evaluation.json").read_text(encoding="utf-8"))
    for n, info in enumerate(neural["candidates"]):
        if not all(f["converged"] for f in info["fits"]):
            continue
        file = a.neural / f"candidate_{n}.parquet"
        sources[f"neural_{n}"] = hashlib.sha256(file.read_bytes()).hexdigest()
        candidates.append((f"neural_{n}", 2, info["parameters"], pd.read_parquet(file)))
    config = json.loads(json.dumps(base_config))
    config.update(
        status="validation_selected_research_candidate_not_default",
        created_at=datetime.now(UTC).isoformat(),
    )
    report = {
        "created_at": config["created_at"],
        "dataset_sha256": base_config["dataset_sha256"],
        "selection_period": ["2022-07-01", "2024-07-01"],
        "diagnostic_period": ["2024-07-01", "2026-07-01"],
        "interpretation": "Repeated exploratory comparisons of inspected historical periods; not a new untouched holdout",
        "prediction_hashes": sources,
        "leagues": {},
    }
    for code, settings in base_config["divisions"].items():
        validation = pd.read_parquet(a.baseline / code / "validation.parquet")
        n = [(180, 2), (180, 10), (365, 2), (365, 10)].index(
            (settings["half_life_days"], settings["ridge"])
        )
        baseline = pd.concat(
            [
                blended_frame(validation, n, settings["dc_weight"], settings["temperature"]),
                pd.read_parquet(a.baseline / code / "selected.parquet"),
            ]
        ).set_index("match_id")
        ranking, frames = [], {}
        for identifier, version, parameters, frame in candidates:
            frame = frame[frame.competition_code.eq(code)].set_index("match_id")
            val = frame[frame.date < "2024-07-01"]
            left = baseline.loc[val.index, PROBS].to_numpy()
            y = np.array([("H", "D", "A").index(r) for r in val.result])
            frames[identifier] = frame
            for weight in (0, 0.25, 0.5, 0.75, 1):
                for temperature in (1.0,) if weight == 0 else (0.9, 1.0, 1.1):
                    probabilities = mix(left, val[PROBS].to_numpy(), weight, temperature)
                    ranking.append(
                        {
                            "candidate": identifier,
                            "feature_version": version,
                            "parameters": parameters,
                            "weight": weight,
                            "temperature": temperature,
                            "validation_log_loss": float(
                                -np.log(probabilities[np.arange(len(y)), y]).mean()
                            ),
                        }
                    )
        ranking.sort(key=lambda r: (r["validation_log_loss"], r["weight"], r["candidate"]))
        winner = ranking[0]
        frame = frames[winner["candidate"]]
        output = frame[frame.date >= "2024-07-01"].copy()
        original = baseline.loc[output.index].copy()
        output[PROBS] = mix(
            original[PROBS].to_numpy(),
            output[PROBS].to_numpy(),
            winner["weight"],
            winner["temperature"],
        )
        output = output.reset_index()
        output.to_parquet(a.output_dir / f"{code}.selected.parquet", index=False)
        previous = pd.read_parquet(a.form_v1 / f"{code}.selected.parquet")
        report["leagues"][code] = {
            "selected": winner,
            "validation_ranking": ranking,
            "metrics": summarize(output),
            "baseline_metrics": summarize(original.reset_index()),
            "vs_baseline": paired_week_bootstrap(output, original.reset_index()),
            "vs_previous_form": paired_week_bootstrap(output, previous),
            "by_season": {s: summarize(g) for s, g in output.groupby("season")},
        }
        config["divisions"][code].update(
            form_weight=winner["weight"],
            form_temperature=winner["temperature"],
            form_parameters=winner["parameters"],
            form_feature_version=winner["feature_version"],
        )
        print(
            code, winner, "diagnostic", report["leagues"][code]["metrics"]["log_loss"], flush=True
        )
    for name, obj in [("evaluation.json", report), ("candidate_config.json", config)]:
        (a.output_dir / name).write_text(
            json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
