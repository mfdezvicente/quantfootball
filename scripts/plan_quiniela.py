"""Generate a budgeted 14-match plan from fixtures or supplied probabilities."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from quantfootball.quiniela.planning import forecast_coupon, plan_coupon

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--fixtures", type=Path, help="JSON array of 14 fixtures to forecast")
    inputs.add_argument("--probabilities", type=Path, help="JSON fixtures with p_home/p_draw/p_away")
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/processed/matches.parquet")
    parser.add_argument("--cutoff", help="Submission date YYYY-MM-DD; Elo excludes this whole day")
    parser.add_argument("--budget", default="5.00")
    parser.add_argument("--model", choices=["elo", "advanced"], default="advanced")
    parser.add_argument("--model-config", type=Path, default=ROOT / "configs/quiniela_model.json")
    parser.add_argument("--pleno", type=Path, help="Optional JSON object for the fifteenth match")
    parser.add_argument("--output", required=True, type=Path, help="New JSON snapshot; never overwritten")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists. Choose a new path to preserve the previous snapshot.")
    if args.fixtures and not args.cutoff:
        parser.error("--fixtures requires --cutoff")
    if args.pleno and (not args.fixtures or args.model != "advanced"):
        parser.error("--pleno requires --fixtures and --model advanced")
    path = args.fixtures or args.probabilities
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        frame = pd.DataFrame(payload)
        inputs_meta = {"input": fingerprint(path)}
        if args.fixtures:
            config = (json.loads(args.model_config.read_text(encoding="utf-8-sig"))
                      if args.model == "advanced" else None)
            pleno = json.loads(args.pleno.read_text(encoding="utf-8-sig")) if args.pleno else None
            frame, model = forecast_coupon(pd.read_parquet(args.dataset), frame, args.cutoff,
                                           model_name=args.model, model_config=config, pleno=pleno)
            inputs_meta["dataset"] = fingerprint(args.dataset)
            if config is not None:
                inputs_meta["model_config"] = fingerprint(args.model_config)
            if args.pleno:
                inputs_meta["pleno"] = fingerprint(args.pleno)
        else:
            model = {"model": "user-supplied probabilities", "temporal_integrity": "not verified"}
        report = plan_coupon(frame, args.budget)
        if "pleno_al_15" in model:
            report["pleno_al_15"] = model["pleno_al_15"]
            report["scope"] = "First 14 coverage plus a standalone Pleno forecast; no prize returns."
            for key in ("full_system", "individual_columns"):
                report[key]["coverage_14_and_pleno"] = (
                    report[key]["coverage"] * model["pleno_al_15"]["recommended_probability"]
                )
    except (ValueError, TypeError, OSError, ImportError, KeyError, RuntimeError) as exc:
        parser.error(str(exc))
    report["model"] = model
    report["inputs"] = inputs_meta
    report["created_at_utc"] = datetime.now(UTC).isoformat()
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    report["code_commit"] = commit
    # Hash executable source too: a commit alone does not identify uncommitted changes.
    source_paths = [Path(__file__), *sorted((ROOT / "src/quantfootball").rglob("*.py"))]
    report["source_sha256"] = {
        str(p.relative_to(ROOT)): fingerprint(p)["sha256"] for p in source_paths
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    print("Quiniela: cobertura estimada de los primeros 14 partidos")
    if "pleno_al_15" in report:
        pleno = report["pleno_al_15"]
        print(f"Pleno al 15: {pleno['recommended_score']} "
              f"(probabilidad estimada {pleno['recommended_probability']:.2%})")
    for key, title in (("full_system", "Sistema completo"), ("individual_columns", "Columnas libres")):
        plan = report[key]
        print(f"{title}: {plan['column_count']} columnas; {plan['cost_eur']} EUR; "
              f"P(14) estimada = {plan['coverage']:.6%}")
    for fixture, signs in zip(report["fixtures"], report["full_system"]["selections"]):
        print(f"{fixture['position']:2}. {fixture['home_team']} - {fixture['away_team']}: "
              f"{''.join(signs)}")
    print(f"Snapshot: {args.output}")


if __name__ == "__main__":
    main()
