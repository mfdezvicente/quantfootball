"""Replay, freeze and score an archived contextual calibrator on paired fixtures."""

import argparse
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from quantfootball.data.active import inspect_inputs, require_ready
from quantfootball.data.competitions import GENDERS
from quantfootball.data.results import ResultLookup
from quantfootball.market.snapshots import instant, key
from quantfootball.models.calibration import calibrate_probabilities
from quantfootball.models.divisions import forecast_divisions
from quantfootball.quiniela.registry import digest, write_new
from quantfootball.research.context_calibration import apply_context
from quantfootball.research.diagnostics import LABELS, PROBS, metrics, paired_delta
from quantfootball.research.flexible_goals import FlexibleGoalModel

MADRID = ZoneInfo("Europe/Madrid")
SLUGS = {"es.1": "laliga-easports", "es.w.1": "futbol-femenino"}
FIXTURE_FIELDS = ("match_id", "date", "competition_code", "gender", "home_team", "away_team")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_design(path):
    design = read(path)
    if design["schema_version"] != 1 or set(design["competitions"]) != set(SLUGS):
        raise ValueError("Unsupported contextual calibration protocol.")
    config_path = Path(design["comparator_config"])
    if digest(config_path) != design["comparator_config_sha256"]:
        raise ValueError("Base configuration does not match the signed-off protocol.")
    config, calibrators = read(config_path), {}
    for code, source in design["competitions"].items():
        archive = Path(source["archive"])
        if digest(archive) != source["archive_sha256"]:
            raise ValueError(f"Archived calibration changed for {code}.")
        calibrators[code] = read(archive)["all_diagnostics"]["reference/context"]["calibration_fit"]
    return design, config, calibrators


def predict_pairs(history, fixtures, cutoff, config, calibrators):
    boundary = pd.Timestamp(cutoff)
    prior = history.loc[history.date < boundary]
    # The archived challenger replaces the final calibration of the shared raw pool.
    raw_config = deepcopy(config)
    for settings in raw_config["divisions"].values():
        settings.pop("calibration", None)
    frame, _, fit = forecast_divisions(
        prior, pd.DataFrame(fixtures), cutoff, raw_config, draws=2, allow_cold_start=True
    )
    if pd.Timestamp(fit["training_last_date"]) >= boundary:
        raise ValueError("Found a result at or after the shared forecast cutoff.")

    pairs = []
    for code, part in frame.groupby("competition_code", sort=True):
        settings, challenger = config["divisions"][code], calibrators[code]
        incumbent = settings["calibration"]
        for calibration in (incumbent, challenger):
            if not (
                pd.Timestamp(calibration["training_last_date"])
                < pd.Timestamp(calibration["selected_before"])
                <= boundary
            ):
                raise ValueError(f"Calibration for {code} has invalid chronology.")
        eligible = part.loc[~part.cold_start].copy()
        if not eligible.empty:
            goal = FlexibleGoalModel(
                family="poisson",
                **{name: settings[name] for name in ("half_life_days", "ridge", "lookback_days")},
            ).fit(prior.loc[prior.competition_code.eq(code)], cutoff)
            eligible["expected_total_goals"] = [
                sum(goal.expected_goals(m.home_team, m.away_team))
                for m in eligible.itertuples(index=False)
            ]
            base = calibrate_probabilities(eligible[PROBS].to_numpy(), incumbent)
            predictions = apply_context(eligible, challenger)
            for (_, row), a, b in zip(eligible.iterrows(), base, predictions, strict=True):
                pairs.append(
                    {
                        **fixture_record(row, cutoff),
                        "expected_total_goals": row["expected_total_goals"],
                        "base": dict(zip(PROBS, a.tolist())),
                        "context": dict(zip(PROBS, b.tolist())),
                    }
                )
        pairs.extend(
            {**fixture_record(row, cutoff), "exclusion": "cold_start"}
            for _, row in part.loc[part.cold_start].iterrows()
        )
    return sorted(pairs, key=lambda item: (item["date"], item["match_id"]))


def fixture_record(row, cutoff):
    fields = {name: row[name] for name in FIXTURE_FIELDS if name != "date"}
    if "starts_at" in row:
        fields["starts_at"] = row["starts_at"]
    return {**fields, "date": pd.Timestamp(row["date"]).date().isoformat(), "cutoff": cutoff}


def class_scores(frame):
    reports = {}
    for label, name in zip(LABELS, PROBS, strict=True):
        p = frame[name].to_numpy()
        observed = frame.result.eq(label).to_numpy()
        bins = []
        for low, high in zip((0, .1, .2, .3, .4, .5, .7), (.1, .2, .3, .4, .5, .7, 1.01)):
            selected = (p >= low) & (p < high)
            bins.append(
                {
                    "lower": low, "upper": min(high, 1), "matches": int(selected.sum()),
                    "probability": float(p[selected].mean()) if selected.any() else None,
                    "frequency": float(observed[selected].mean()) if selected.any() else None,
                }
            )
        reports[label] = {
            "probability": float(p.mean()), "frequency": float(observed.mean()),
            "brier": float(np.square(p - observed).mean()), "bins": bins,
        }
    return reports


def summarize(pairs, labels):
    leagues = {}
    for code in SLUGS:
        rows = [r for r in pairs if r["competition_code"] == code]
        usable = [r for r in rows if "exclusion" not in r]
        complete = [r for r in usable if r["match_id"] in labels]
        entry = {
            "completed": len(complete), "pending": len(usable) - len(complete),
            "excluded_cold_start": len(rows) - len(usable),
        }
        if complete:
            frames = {}
            for model in ("base", "context"):
                frame = pd.DataFrame(
                    {**r[model], "result": labels[r["match_id"]],
                     "date": r["date"], "match_id": r["match_id"]}
                    for r in complete
                )
                frames[model] = frame
                entry[model] = {**metrics(frame), "classes": class_scores(frame)}
            entry["context_minus_base"] = paired_delta(frames["context"], frames["base"])
        leagues[code] = entry
    return leagues


def schedule(paths, now, max_lead_days):
    fixtures, sources = [], {}
    for path in paths:
        source = read(path)
        code = path.stem.split("-")[1]
        if code not in SLUGS:
            raise ValueError(f"Unsupported scheduled competition in {path.name}.")
        url = (
            f"https://www.laliga.com/{SLUGS[code]}/resultados/"
            f"{source['season']}/jornada-{source['matchday']}"
        )
        if source["source_url"] != url or instant(source["fetched_at"]) > now:
            raise ValueError(f"Unverified schedule provenance in {path.name}.")
        sources[path.name] = {"sha256": digest(path), "url": url, "captured": source["fetched_at"]}
        for match in source["matches"]:
            kickoff = instant(match["date"])
            if not (
                now < kickoff <= now + timedelta(days=max_lead_days)
                and match["status"] == "PreMatch"
                and match["home_score"] is None
                and match["away_score"] is None
            ):
                raise ValueError(f"Fixture {match['id']} is outside the future pre-match window.")
            fixture = {
                "match_id": f"{code}:laliga:{match['id']}",
                "competition_code": code,
                "gender": GENDERS[code],
                "home_team": match["home_team"],
                "away_team": match["away_team"],
                "date": kickoff.astimezone(MADRID).date().isoformat(),
                "starts_at": kickoff.isoformat(),
            }
            _, fixture["home_team"], fixture["away_team"] = key(fixture)
            fixtures.append(fixture)
    keys = {(*key(f), f["date"]) for f in fixtures}
    if not fixtures or len({f["match_id"] for f in fixtures}) != len(fixtures) or len(keys) != len(fixtures):
        raise ValueError("Supply unique future fixtures.")
    return fixtures, sources


def freeze(args, history, design, config, calibrators):
    now = datetime.now(UTC)
    cutoff = now.astimezone(MADRID).date().isoformat()
    if not design["prospective_start_inclusive"] <= cutoff < design["prospective_end_exclusive"]:
        raise ValueError("Forecast is outside the protocol evaluation period.")
    if history.date.max() >= pd.Timestamp(cutoff):
        raise ValueError("Prospective input dataset must end strictly before the forecast date.")
    fixtures, sources = schedule(args.schedule, now, design["forecast_max_lead_days"])
    required = {f["competition_code"] for f in fixtures}
    require_ready(inspect_inputs(args.dataset, design["comparator_config"], cutoff, required=required))
    pairs = predict_pairs(history, fixtures, cutoff, config, calibrators)
    sealed_at = datetime.now(UTC)
    if any(instant(row["starts_at"]) <= sealed_at for row in pairs):
        raise ValueError("A fixture kicked off during forecast generation.")
    payload = {
        "schema_version": 1, "mode": "prospective", "sealed_at": sealed_at.isoformat(),
        "protocol_sha256": digest(args.protocol), "dataset_sha256": digest(args.dataset),
        "program_sha256": digest(Path(__file__)),
        "base_module_sha256": digest(Path("src/quantfootball/models/divisions.py")),
        "calibration_module_sha256": digest(Path("src/quantfootball/research/context_calibration.py")),
        "schedule_sources": sources,
        "pairs": pairs,
    }
    args.output.mkdir(parents=True, exist_ok=False)
    write_new(args.output / "forecast.json", payload)
    write_new(args.output / "seal.json", {"forecast_sha256": digest(args.output / "forecast.json")})
    print(f"Recorded {sum('exclusion' not in p for p in pairs)} pre-kickoff pairs", flush=True)


def replay(args, history, design, config, calibrators):
    sample = history.loc[
        history.competition_code.isin(calibrators)
        & (history.date >= pd.Timestamp(design["historical_replay_start_inclusive"]))
        & (history.date < pd.Timestamp(args.end))
    ].copy()
    if sample.empty:
        raise ValueError("No fixtures in the replay window.")
    sample["cutoff"] = sample.date - pd.to_timedelta(sample.date.dt.dayofweek, unit="D")
    pairs = []
    for cutoff, group in sample.groupby("cutoff", sort=True):
        pairs.extend(
            predict_pairs(history, group[list(FIXTURE_FIELDS)].to_dict("records"),
                          cutoff.date().isoformat(), config, calibrators)
        )
        print(f"{cutoff.date()}  {len(group)} fixtures", flush=True)
    labels = sample.set_index("match_id").result.to_dict()
    leagues = summarize(pairs, labels)
    args.output.mkdir(parents=True, exist_ok=False)
    write_new(args.output / "report.json", {
        "schema_version": 1, "mode": "historical_replay", "end_exclusive": args.end,
        "protocol_sha256": digest(args.protocol), "dataset_sha256": digest(args.dataset),
        "leagues": leagues,
        "limitations": [
            "Archived final calendar, reconstructed Madrid Monday cutoffs and local result dates.",
            "Exploratory 2026/27 sample includes previously inspected matches.",
        ],
        "pairs": [{**r, "result": labels[r["match_id"]]} for r in pairs],
    })
    print_summary(leagues)


def evaluate(args, history, design):
    now = datetime.now(UTC)
    records = []
    for folder in args.forecast:
        path = folder / "forecast.json"
        if digest(path) != read(folder / "seal.json")["forecast_sha256"]:
            raise ValueError("Prospective forecast hash does not match the seal.")
        report = read(path)
        stamp = instant(report["sealed_at"])
        day = stamp.astimezone(MADRID).date().isoformat()
        if (report["mode"] != "prospective" or digest(args.protocol) != report["protocol_sha256"]
                or stamp > now
                or not design["prospective_start_inclusive"] <= day < design["prospective_end_exclusive"]):
            raise ValueError("Forecast is not eligible under this prospective protocol.")
        for row in report["pairs"]:
            if stamp >= instant(row["starts_at"]):
                raise ValueError("Forecast was sealed after a fixture had started.")
            records.append((stamp, row))
    lookup, used, pairs, labels = ResultLookup(history), set(), [], {}
    duplicates = 0
    for stamp, row in sorted(records, key=lambda x: (x[0], x[1]["match_id"])):
        match_id = row["match_id"]
        if match_id in used:
            duplicates += 1
            continue
        used.add(match_id)
        pairs.append(row)
        if "exclusion" in row:
            continue
        result = lookup.find(row, stamp)
        if result is not None:
            labels[match_id] = result["result"]
    leagues = summarize(pairs, labels)
    write_new(args.output, {
        "schema_version": 1, "mode": "prospective_evaluation",
        "protocol_sha256": digest(args.protocol), "dataset_sha256": digest(args.dataset),
        "evaluated_at": now.isoformat(), "deduplicated_matches": duplicates,
        "sources": {str(folder): digest(folder / "forecast.json") for folder in args.forecast},
        "leagues": leagues, "results": labels,
    })
    print_summary(leagues)


def print_summary(leagues):
    for code, entry in leagues.items():
        loss = entry.get("context_minus_base", {}).get("mean_log_loss_difference")
        print(code, "completed", entry["completed"], "pending", entry["pending"],
              "excluded", entry["excluded_cold_start"], "delta log loss", loss, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("replay", "freeze", "evaluate"):
        sub = commands.add_parser(command)
        sub.add_argument("--dataset", required=True, type=Path)
        sub.add_argument("--protocol", required=True, type=Path)
        sub.add_argument("--output", required=True, type=Path)
    commands.choices["replay"].add_argument("--end", required=True)
    commands.choices["freeze"].add_argument("--schedule", required=True, type=Path, nargs="+")
    commands.choices["evaluate"].add_argument("--forecast", required=True, type=Path, nargs="+")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output to preserve previous research.")
    design, config, calibrators = load_design(args.protocol)
    history = pd.read_parquet(args.dataset)
    history["date"] = pd.to_datetime(history.date)
    if args.command == "evaluate":
        evaluate(args, history, design)
    elif args.command == "freeze":
        freeze(args, history, design, config, calibrators)
    else:
        replay(args, history, design, config, calibrators)


if __name__ == "__main__":
    main()
