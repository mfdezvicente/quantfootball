"""One explicit paper run: validate, generate frozen pair, register odds and abstention.

No scheduler, secret handling, odds downloads or purchases. Supply an already
captured current market snapshot and a verified future official observation.
"""

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from quantfootball.data.active import inspect_inputs, require_ready, resolve_active
from quantfootball.market.prospective import attach_market, register_pair
from quantfootball.market.snapshots import compare_snapshot
from quantfootball.quiniela.decision import (
    SCOPE,
    register_decision,
    validate_observation,
    verify_decision,
)
from quantfootball.quiniela.registry import digest, write_new

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("observation", "snapshot", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--dataset", type=Path, help="Defaults to the active snapshot")
    parser.add_argument("--draws", type=int, default=64)
    parser.add_argument("--pair-root", type=Path, default=ROOT / "outputs/predictions/probability_pairs_pool50")
    parser.add_argument("--decision-root", type=Path, default=ROOT / "outputs/predictions/economic_decisions")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    status = {"created_at": datetime.now(UTC).isoformat(), "paper_only": True,
              "registered_pair": False, "registered_decision": False,
              "inputs_sha256": {}}
    try:
        status["inputs_sha256"] = {str(p.resolve()): digest(p) for p in (args.observation, args.snapshot)}
        obs = json.loads(args.observation.read_text(encoding="utf-8"))
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        now = datetime.now(UTC)
        validate_observation(obs, now)
        # Record a real pre-close economic abstention even if the research run later fails.
        decision_folder = args.decision_root / obs["contest_id"]
        if decision_folder.exists():
            verify_decision(decision_folder)
            if digest(decision_folder / "observation.json") != digest(args.observation):
                raise ValueError("Existing immutable decision uses a different official observation.")
        else:
            register_decision(args.observation, args.decision_root)
        status["registered_decision"] = True
        if any(SCOPE.get(f["competition_code"]) != f.get("gender") for f in obs["fixtures"]):
            raise ValueError("Full coupon outside the three eligible competitions.")
        active = resolve_active(ROOT)
        args.dataset = args.dataset or active["dataset"]
        # Comparator parameters are frozen by the declared pool protocol.
        comparator = ROOT / "configs/quiniela_dynamic_candidate.json"
        protocol = json.loads((ROOT / "configs/market_pool50_protocol_20261014.json").read_text(encoding="utf-8"))
        if digest(comparator) != protocol["comparator_config_sha256"]:
            raise ValueError("Frozen comparator configuration changed.")
        status["input_preflight"] = inspect_inputs(
            args.dataset, comparator, now.astimezone(ZoneInfo("Europe/Madrid")).date().isoformat(),
            active["max_result_age_days"])
        status["inputs_sha256"][str(args.dataset.resolve())] = digest(args.dataset)
        status["active_manifest_sha256"] = active["manifest_sha256"]
        require_ready(status["input_preflight"])
        for root in (args.pair_root,):
            if (root / obs["contest_id"]).exists():
                raise ValueError("This probability pair is already registered; no replacement is allowed.")
        fixtures_path, pleno_path = args.output_dir / "fixtures.json", args.output_dir / "pleno.json"
        write_new(fixtures_path, obs["fixtures"][:14])
        write_new(pleno_path, obs["fixtures"][14])
        base, pool = args.output_dir / "base", args.output_dir / "pool50"
        def run(script, *parameters):
            subprocess.run([sys.executable, str(ROOT / "scripts" / script), *map(str, parameters)], check=True, cwd=ROOT)
        run("plan_spain.py", "--fixtures", fixtures_path.resolve(), "--pleno", pleno_path.resolve(),
            "--official-observation", args.observation.resolve(), "--dataset", args.dataset.resolve(),
            "--cutoff", now.astimezone(ZoneInfo("Europe/Madrid")).date().isoformat(), "--budget", "5.00",
            "--draws", args.draws, "--config", ROOT / "configs/quiniela_dynamic_candidate.json", "--output-dir", base.resolve())
        # The official observation has identities, not predictions. Compare actual
        # generated probabilities at the current time (training may take minutes).
        base_report = json.loads((base / "forecast.json").read_text(encoding="utf-8"))
        decision_at = datetime.now(UTC)
        validate_observation(obs, decision_at)
        comparison = compare_snapshot(base_report["coupons"][0], snapshot, decision_at.isoformat())
        covered = {r["position"] for r in comparison["fixtures"]}
        if (comparison["is_example"] or not comparison["available_to_this_app_before_decision"]
                or any(f["competition_code"] != "es.w.1" and f["position"] not in covered
                       for f in obs["fixtures"][:14])):
            raise ValueError("Missing eligible contemporaneous men's market data.")
        status["market_preflight"] = {"checked_at": decision_at.isoformat(),
                                      "matched_fixtures": comparison["matched_fixtures"],
                                      "missing": comparison["missing"]}
        run("plan_market_pool.py", "--base-forecast", base.resolve() / "forecast.json", "--scenarios", base.resolve() / "scenarios.npz",
            "--snapshot", args.snapshot.resolve(), "--official-observation", args.observation.resolve(),
            "--config", ROOT / "configs/market_pool50_20261014.json", "--output-dir", pool.resolve())
        register_pair(pool / "forecast.json", base / "forecast.json", args.observation,
                      ROOT / "configs/market_pool50_protocol_20261014.json", args.pair_root)
        status["registered_pair"] = True
        candidate = json.loads((pool / "forecast.json").read_text(encoding="utf-8"))
        market_path = args.output_dir / "comparison.json"
        write_new(market_path, candidate["coupons"][0]["market_comparison"])
        attach_market(args.pair_root / obs["contest_id"], market_path)
        status["status"] = "completed"
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        status.update(status="blocked_or_partial", reason=str(exc))
    write_new(args.output_dir / "run_status.json", status)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if status["status"] != "completed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
