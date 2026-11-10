"""Reconstruct the frozen base model inputs for the closed J20 coupon."""

import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from quantfootball.data.competitions import GENDERS, women_team_name
from quantfootball.data.current import update_snapshot
from quantfootball.data.teams import canonicalize_team
from quantfootball.quiniela.registry import digest, write_new

ROOT = Path.cwd()
STAGE = Path(__file__).resolve().parent
SNAPSHOTS = ROOT / "outputs/reports/j18_evaluation_20261110/public_results"
DATASET = STAGE / "matches_j20_before_20261107.parquet"
CONFIG = ROOT / "configs/quiniela_dynamic_candidate.json"
CUTOFF = "2026-11-07"
MADRID = ZoneInfo("Europe/Madrid")
OFFICIAL_RESULTS = (
    "https://www.loteriasyapuestas.es/es/la-quiniela/escrutinios/"
    "la-quiniela-premios-y-ganadores-del-08-de-noviembre-de-2026"
)
OFFICIAL_POSTPONEMENT = (
    "https://www.selae.es/f/loterias/web_corporativa/Comunicacion/Avisos_de_interes/"
    "APLAZAMIENTO%20JORNADA%2020%20DE%20LA%20QUINIELA%207_8%20NOVIEMBRE%202026%20(002).pdf"
)
POSITIONS = [
    ("es.1", 12, "Málaga CF", "Racing Santander"),
    ("es.1", 12, "CA Osasuna", "Athletic Club"),
    ("es.1", 12, "Valencia CF", "Real Madrid CF"),
    ("es.1", 12, "Elche CF", "Real Betis Balompié"),
    ("es.1", 12, "Real Sociedad de Fútbol", "Rayo Vallecano de Madrid"),
    ("es.1", 12, "RC Celta de Vigo", "Levante UD"),
    ("es.1", 12, "Villarreal CF", "Getafe CF"),
    ("es.2", 13, "Cádiz CF", "Real Oviedo"),
    ("es.2", 13, "Girona FC", "UD Almería"),
    ("es.2", 13, "Sporting Gijón", "Real Valladolid CF"),
    ("es.w.1", 10, "Athletic Club [F]", "Real Madrid CF [F]"),
    ("es.w.1", 10, "Logroño United [F]", "Sevilla FC [F]"),
    ("es.w.1", 10, "SD Eibar [F]", "Real Sociedad [F]"),
    ("es.w.1", 10, "Costa Adeje Tenerife [F]", "Deportivo Alavés [F]"),
    ("es.1", 12, "Club Atlético de Madrid", "FC Barcelona"),
]


def main():
    protocol = json.loads((ROOT / "configs/market_pool50_protocol_20261014.json").read_text(encoding="utf-8"))
    assert digest(CONFIG) == protocol["comparator_config_sha256"]
    fixtures = []
    for position, (code, round_no, home, away) in enumerate(POSITIONS, 1):
        path = SNAPSHOTS / f"2026-{code}-{round_no:02}.json"
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        normalize = women_team_name if code == "es.w.1" else canonicalize_team
        matching = [m for m in snapshot["matches"] if (
            normalize(m["home_team"]), normalize(m["away_team"])
        ) == (home, away)]
        assert len(matching) == 1, (position, code, home, away)
        fixture = matching[0]
        kickoff = datetime.fromisoformat(fixture["date"]).astimezone(MADRID)
        assert kickoff.date().isoformat() >= CUTOFF
        fixtures.append({
            "position": position, "competition_code": code, "gender": GENDERS[code],
            "home_team": home, "away_team": away, "date": kickoff.date().isoformat(),
            "starts_at": kickoff.isoformat(), "league_match_id": fixture["id"],
            "schedule_source_url": snapshot["source_url"],
            "schedule_observed_at": snapshot["fetched_at"],
        })
    write_new(STAGE / "fixtures.json", fixtures[:14])
    write_new(STAGE / "pleno.json", fixtures[14])
    audit = update_snapshot(
        ROOT / "data/processed/matches_quiniela_20261028.parquet", [SNAPSHOTS], DATASET, CUTOFF
    )
    history = pd.read_parquet(DATASET)
    assert history.date.max() < pd.Timestamp(CUTOFF)
    season = history.loc[history.season.eq("2026-27")]
    fixture_keys = {(f["competition_code"], f["home_team"], f["away_team"]) for f in fixtures}
    trained_keys = set(season[["competition_code", "home_team", "away_team"]].itertuples(index=False, name=None))
    assert not trained_keys.intersection(fixture_keys)
    write_new(STAGE / "design.json", {
        "contest_id": "2026_j20", "contest_date": "2026-11-08",
        "created_at": datetime.now(UTC).isoformat(), "retrospective": True,
        "prospective_registry_eligible": False,
        "cutoff_exclusive_madrid": "2026-11-07T00:00:00+01:00",
        "earliest_listed_kickoff_madrid": min(f["starts_at"] for f in fixtures),
        "cutoff_reason": "Conservative calendar cutoff before first kickoff and reported sales cutoffs; exact SELAE closing time unverified",
        "sports_data": "Reconstructed from later captures of earlier completed matches, not a contemporaneous archive",
        "excluded_j20_fixtures_from_training": len(fixtures),
        "source_coupon_order": OFFICIAL_RESULTS,
        "training_rows": len(history), "training_last_dates": audit["last_dates"],
        "dataset_sha256": digest(DATASET), "config_sha256": digest(CONFIG),
        "model": "Frozen standalone base configuration used as J18 comparator",
        "primary_strategy": protocol["primary_strategy"],
        "budget_cap_eur": protocol["maximum_budget_eur"], "bootstrap_draws": 64,
        "uses_market_quotes": False,
        "market_reason": "No eligible archived J20 pre-close odds in the project",
        "sporting_metrics_exclusions": [{"position": 14, "reason": "Official lottery draw after postponement",
                                          "source_url": OFFICIAL_POSTPONEMENT}],
        "settlement_policy": "Apply all fourteen SELAE signs to the frozen columns; compare sporting probabilities on played games only",
        "evaluation_source_accessed_before_model_run": True,
        "policy_selection": "Same predeclared J18 comparator configuration, budget and primary strategy without reselecting using J20 results",
    })
    print(json.dumps({"training_rows": len(history), "last_dates": audit["last_dates"],
                      "coupon_fixtures_held_out": len(fixtures)}, indent=2))


if __name__ == "__main__":
    main()
