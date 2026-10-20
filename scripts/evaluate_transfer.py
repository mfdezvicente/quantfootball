"""Select promotion-aware mixtures on 2022-24; report chronological 2024-26 diagnostics."""

import argparse
import hashlib
import itertools
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from quantfootball.evaluation.advanced import blended_frame, paired_week_bootstrap, summarize
from quantfootball.models.transfer_elo import TransferElo

ROOT = Path(__file__).resolve().parents[1]
PROBS = ["p_home", "p_draw", "p_away"]


def score(probabilities, results):
    targets = np.array([("H", "D", "A").index(x) for x in results])
    return float(-np.log(probabilities[np.arange(len(targets)), targets]).mean())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=ROOT / "outputs/reports/spain_v5")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("Choose a new experiment directory.")
    args.output_dir.mkdir(parents=True)
    path = ROOT / "data/processed/matches_spain.parquet"
    data = pd.read_parquet(path).sort_values(["date", "home_team"], kind="stable")
    frozen = json.loads((args.baseline / "model_config.json").read_text(encoding="utf-8"))
    if hashlib.sha256(path.read_bytes()).hexdigest() != frozen["dataset_sha256"]:
        raise ValueError("Baseline dataset differs; regenerate its predictions first.")
    baseline = {}
    for code in ("es.1", "es.2"):
        config = frozen["divisions"][code]
        validation = pd.read_parquet(args.baseline / code / "validation.parquet")
        candidate = [(180, 2), (180, 10), (365, 2), (365, 10)].index(
            (config["half_life_days"], config["ridge"])
        )
        selected = blended_frame(validation, candidate, config["dc_weight"], config["temperature"])
        diagnostic = pd.read_parquet(args.baseline / code / "selected.parquet")
        baseline[code] = pd.concat([selected, diagnostic]).set_index("match_id")
    targets = data[(data.date >= "2022-07-01") & (data.date < "2026-07-01")].copy()
    targets["cutoff"] = targets.date - pd.to_timedelta(targets.date.dt.dayofweek, unit="D")
    candidates = [
        dict(zip(("league_gap", "carryover", "newcomer_penalty"), x))
        for x in itertools.product((0.0, 100.0, 200.0, 300.0), (0.75, 1.0), (0.0, 80.0))
    ]
    records = list(data.itertuples(index=False))
    predictions = []
    for number, settings in enumerate(candidates):
        model = TransferElo(**settings)
        cursor = 0
        rows = []
        for cutoff, group in targets.groupby("cutoff", sort=True):
            while cursor < len(records) and records[cursor].date < cutoff:
                m = records[cursor]
                model.update(m.home_team, m.away_team, m.competition_code, m.season, m.result)
                cursor += 1
            for m in group.itertuples(index=False):
                p = model.predict_proba(m.home_team, m.away_team, m.competition_code, m.season)
                previous = [model.state.get(t) for t in (m.home_team, m.away_team)]
                transferred = any(s and s["code"] != m.competition_code for s in previous)
                rows.append(
                    {
                        "match_id": m.match_id,
                        "competition_code": m.competition_code,
                        "date": m.date,
                        "cutoff": cutoff.isoformat(),
                        "season": m.season,
                        "result": m.result,
                        "transfer_at_cutoff": bool(transferred),
                        "candidate": number,
                        **dict(zip(PROBS, p.values())),
                    }
                )
        predictions.append(pd.DataFrame(rows))
        print("Transfer candidate", number + 1, "/", len(candidates), settings, flush=True)
    all_predictions = pd.concat(predictions, ignore_index=True)
    all_predictions.to_parquet(args.output_dir / "transfer_predictions.parquet", index=False)
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "leagues": {},
        "dataset_sha256": frozen["dataset_sha256"],
        "selection_period": ["2022-07-01", "2024-07-01"],
        "diagnostic_period": ["2024-07-01", "2026-07-01"],
        "interpretation": "Retrospective experiment; already inspected periods, not an untouched holdout",
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__), ROOT / "src/quantfootball/models/transfer_elo.py"]
        },
    }
    deployment = json.loads(json.dumps(frozen))
    deployment["base_config_created_at"] = frozen.get("created_at")
    deployment["created_at"] = report["created_at"]
    deployment["status"] = "experimental_candidate_not_default"
    for code, base in baseline.items():
        ranking = []
        for number, settings in enumerate(candidates):
            frame = all_predictions[
                (all_predictions.candidate == number) & (all_predictions.competition_code == code)
            ].set_index("match_id")
            val = frame[frame.date < "2024-07-01"]
            b = base.reindex(val.index)[PROBS].to_numpy()
            t = val[PROBS].to_numpy()
            for weight in (0.0, 0.25, 0.5, 1.0):
                ranking.append(
                    {
                        "candidate": number,
                        "weight": weight,
                        "parameters": settings,
                        "log_loss": score((1 - weight) * b + weight * t, val.result),
                    }
                )
        ranking.sort(key=lambda x: (x["log_loss"], x["weight"], x["candidate"]))
        winner = ranking[0]
        frame = all_predictions[
            (all_predictions.candidate == winner["candidate"])
            & (all_predictions.competition_code == code)
        ].set_index("match_id")
        frame = frame[frame.date >= "2024-07-01"].copy()
        aligned = base.reindex(frame.index).copy()
        frame[PROBS] = (1 - winner["weight"]) * aligned[PROBS] + winner["weight"] * frame[PROBS]
        frame = frame.reset_index()
        aligned = aligned.reset_index()
        frame.to_parquet(args.output_dir / f"{code}.selected.parquet", index=False)
        report["leagues"][code] = {
            "selected": winner,
            "ranking": ranking,
            "metrics": summarize(frame),
            "baseline_metrics": summarize(aligned),
            "vs_baseline": paired_week_bootstrap(frame, aligned),
            "by_season": {s: summarize(g) for s, g in frame.groupby("season")},
        }
        # Record a research candidate; promotion to default is a separate documented decision.
        deployment["divisions"][code]["transfer_weight"] = winner["weight"]
        deployment["divisions"][code]["transfer_parameters"] = winner["parameters"]
        print(
            code,
            winner,
            "diagnostic",
            report["leagues"][code]["metrics"]["log_loss"],
            report["leagues"][code]["vs_baseline"],
            flush=True,
        )
    (args.output_dir / "evaluation.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    (args.output_dir / "candidate_config.json").write_text(
        json.dumps(deployment, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
