"""Forecast an authorized current odds snapshot and seal pre-kickoff comparisons."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from quantfootball.market.match_study import evaluate_studies, save, seal_study
from quantfootball.market.snapshots import compare_snapshot, instant
from quantfootball.models.divisions import forecast_divisions

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/quiniela_dynamic_candidate.json")
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--draws", type=int, default=64)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("Choose a new immutable study directory.")
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    now = datetime.now(UTC)
    if snapshot.get("is_example") or instant(snapshot["retrieved_at"]) > now:
        parser.error("An actual already-retrieved snapshot is required.")
    eligible, excluded = [], []
    for fixture in snapshot["fixtures"]:
        if now >= instant(fixture["starts_at"]):
            excluded.append({"event_id": fixture.get("provider_event_id"), "reason": "already_started_before_prediction"})
            continue
        local = instant(fixture["starts_at"]).astimezone(ZoneInfo("Europe/Madrid")).date().isoformat()
        eligible.append({**{k: fixture[k] for k in ("competition_code", "gender", "home_team", "away_team", "starts_at")},
                         "date": local, "position": len(eligible) + 1})
    if not eligible:
        parser.error("No eligible upcoming matches.")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    predictions, scenarios, model = forecast_divisions(pd.read_parquet(args.dataset), pd.DataFrame(eligible), args.cutoff, config, draws=args.draws)
    rows = json.loads(predictions.to_json(orient="records", date_format="iso"))
    # The common decision is after inference; quotes have been possessed since retrieval.
    decision = datetime.now(UTC).isoformat()
    comparison = compare_snapshot({"fixtures": rows}, snapshot, decision)
    report = {"schema_version": 1, "is_example": False, "scope": "sporting_match_probabilities_only",
        "created_at": datetime.now(UTC).isoformat(), "cutoff": args.cutoff,
        "snapshot_at": snapshot["snapshot_at"], "fixtures": rows, "model": model, "config": config,
        "comparison": comparison, "excluded_before_results": excluded,
        "inputs_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for name, path in (("snapshot", args.snapshot), ("dataset", args.dataset), ("config", args.config))},
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in [Path(__file__), *sorted((ROOT / "src/quantfootball").rglob("*.py"))]},
        "paper_only": True, "full_ticket_roi_eligible": False,
        "positive_expected_roi_demonstrated": False,
        "context": "Current match probability benchmark; not an official coupon or pre-close reconstruction of jornada 11"}
    args.output_dir.mkdir(parents=True, exist_ok=False)
    save(args.output_dir / "forecast.json", report)
    for name, original in (("snapshot.json", args.snapshot), ("config.json", args.config)):
        with (args.output_dir / name).open("xb") as handle:
            handle.write(original.read_bytes())
    predictions.to_parquet(args.output_dir / "predictions.parquet", index=False)
    np.savez_compressed(args.output_dir / "scenarios.npz", probabilities=scenarios)
    seal_study(args.output_dir)
    from quantfootball.market.match_dashboard import render_market_study
    render_market_study(report, args.output_dir / "dashboard.html")
    status = evaluate_studies(args.output_dir.parent, args.dataset)
    save(args.output_dir / "initial_evaluation.json", status)
    print(f"Locally sealed {comparison['matched_fixtures']}/{len(rows)} actual model/market pairs; no ROI inferred.")


if __name__ == "__main__":
    main()
