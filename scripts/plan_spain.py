"""Generate a frozen mixed Primera/Segunda forecast, strategies and local HTML."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from quantfootball.data.active import inspect_inputs, require_ready, resolve_active
from quantfootball.data.competitions import GENDERS, women_team_name
from quantfootball.data.teams import canonicalize_team
from quantfootball.market.snapshots import instant, key, source_url
from quantfootball.models.divisions import forecast_divisions
from quantfootball.models.dixon_coles import DixonColesModel
from quantfootball.quiniela.dashboard import render_dashboard
from quantfootball.quiniela.planning import validate_fixtures
from quantfootball.quiniela.uncertainty import compare_strategies

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--budget", default="5.00")
    parser.add_argument("--draws", type=int, default=64)
    parser.add_argument("--example", action="store_true", help="Label illustrative fixtures; reject prospective registration")
    parser.add_argument("--pleno", type=Path)
    parser.add_argument("--official-observation", type=Path,
                        help="Reviewed official coupon and kickoff observation; does not register a full ticket")
    parser.add_argument(
        "--dataset", type=Path, help="Explicit historical/research snapshot; otherwise use the active manifest"
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--evaluation", type=Path, default=ROOT / "outputs/reports/spain_v5/evaluation.json"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    a = parser.parse_args()
    if a.output_dir.exists():
        parser.error("Choose a new output directory to preserve prediction history.")
    if not Decimal("1.50") <= Decimal(a.budget) <= Decimal("10.00"):
        parser.error("Budget must be between 1.50 and 10.00 EUR.")
    frame = validate_fixtures(pd.DataFrame(json.loads(a.fixtures.read_text(encoding="utf-8-sig"))))
    observation = None
    if a.official_observation:
        observation = json.loads(a.official_observation.read_text(encoding="utf-8"))
        now = datetime.now(UTC)
        source_url(observation["source_url"])
        if a.example or observation.get("is_example") or not instant(observation["captured_at"]) <= now < instant(observation["closes_at"]):
            parser.error("Official observation must be real, already captured and before deadline.")
        if len(observation["fixtures"]) != 15:
            parser.error("Official observation must identify all fifteen positions.")
        from zoneinfo import ZoneInfo
        for actual, expected in zip(frame.to_dict("records"), observation["fixtures"][:14]):
            kickoff = instant(expected["starts_at"])
            if (actual["position"] != expected["position"] or key(actual) != key(expected)
                or actual["date"].date() != kickoff.astimezone(ZoneInfo("Europe/Madrid")).date()
                or now >= kickoff or instant(observation["closes_at"]) > kickoff):
                parser.error("Fixture order, date or identity differs from the official observation.")
    active = None
    if a.dataset is None or a.config is None:
        active = resolve_active(ROOT)
        a.dataset = a.dataset or active["dataset"]
        a.config = a.config or active["config"]
    required = set(frame.competition_code)
    if a.pleno:
        required.add(json.loads(a.pleno.read_text(encoding="utf-8-sig"))["competition_code"])
    # Official runs always enforce recency; fully explicit historical runs remain reproducible.
    preflight = inspect_inputs(a.dataset, a.config, a.cutoff,
                               (active["max_result_age_days"] if active else 14)
                               if observation or active else None, required)
    require_ready(preflight)
    if active:
        preflight["manifest_sha256"] = active["manifest_sha256"]
    data = pd.read_parquet(a.dataset)
    config = json.loads(a.config.read_text(encoding="utf-8"))
    forecasts, scenarios, metadata = forecast_divisions(
        data, frame, a.cutoff, config, draws=a.draws
    )
    pleno = None
    if a.pleno:
        p = json.loads(a.pleno.read_text(encoding="utf-8-sig"))
        date = pd.Timestamp(p["date"])
        code = p["competition_code"]
        normalizer = women_team_name if code == "es.w.1" else canonicalize_team
        home, away = [normalizer(p[k]) for k in ("home_team", "away_team")]
        if (
            pd.isna(date)
            or date.tz is not None
            or date < pd.Timestamp(a.cutoff)
            or code not in GENDERS
            or p.get("gender", "men") != GENDERS.get(code)
        ):
            parser.error("Pleno requires a valid date, competition and corresponding gender.")
        used = set(frame.home_team) | set(frame.away_team)
        if home in used or away in used or home == away:
            parser.error("Pleno teams must differ from each other and the first fourteen.")
        settings = config["divisions"][code]
        goal = DixonColesModel(
            **{k: settings[k] for k in ("half_life_days", "ridge", "lookback_days")}
        )
        goal.fit(data[data.competition_code.eq(code)], a.cutoff)
        probabilities = goal.predict_pleno(home, away)
        pleno = {
            "home_team": home,
            "away_team": away,
            "prediction": max(probabilities, key=probabilities.get),
            "probabilities": probabilities,
            "date": date.date().isoformat(),
            "competition_code": code,
            "gender": GENDERS[code],
        }
    plans = compare_strategies(
        forecasts[["p_home", "p_draw", "p_away"]].values.tolist(), scenarios, a.budget
    )
    coupon = {
        "date": a.cutoff,
        "cutoff": a.cutoff,
        "fixtures": json.loads(forecasts.to_json(orient="records", date_format="iso")),
        "model": metadata,
        "budgets": {f"{Decimal(a.budget):.2f}": plans},
        "pleno": pleno,
        "label": observation.get("label") if observation else None,
    }
    sources = [a.fixtures, a.dataset, a.config, *([a.pleno] if a.pleno else []),
               *([a.official_observation] if a.official_observation else [])]
    report = {
        "input_preflight": preflight,
        "prospective": False,
        "registration_status": "example" if a.example else "unregistered",
        "is_example": a.example,
        "created_at": datetime.now(UTC).isoformat(),
        "coupons": [coupon],
        "summary": {},
        "excluded": [],
        "inputs": {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__), *sorted((ROOT / "src/quantfootball").rglob("*.py"))]
        },
        "profitable_edge_demonstrated": False,
        "config": config,
        "official_contest": observation,
    }
    a.output_dir.mkdir(parents=True)
    forecasts.to_parquet(a.output_dir / "predictions.parquet", index=False)
    np.savez_compressed(a.output_dir / "scenarios.npz", probabilities=scenarios)
    (a.output_dir / "forecast.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    evaluation = (
        json.loads(a.evaluation.read_text(encoding="utf-8")) if a.evaluation.exists() else {}
    )
    audit_path = a.dataset.with_suffix(".audit.json")
    audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
    render_dashboard(report, evaluation, audit, a.output_dir / "dashboard.html")
    print(a.output_dir / "dashboard.html")


if __name__ == "__main__":
    main()
