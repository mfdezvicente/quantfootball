"""Build a current combined snapshot while preserving the immutable evaluation data."""

import hashlib
import json
from pathlib import Path

import pandas as pd

from quantfootball.data.openfootball import normalize_payload, validate_matches

ROOT = Path(__file__).resolve().parents[1]


def main():
    snapshot = ROOT / "data/raw/current_20261002/laliga"
    men_path = ROOT / "data/processed/matches_spain.parquet"
    women_path = ROOT / "data/processed/matches_ligaf.parquet"
    men = pd.read_parquet(men_path)
    frames, hashes, pending = [], {}, 0
    for file in sorted(snapshot.glob("*.json")):
        raw = json.loads(file.read_text(encoding="utf-8"))
        code = "es.1" if "-es.1-" in file.name else "es.2"
        hashes[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
        matches = []
        for m in raw["matches"]:
            local = pd.Timestamp(m["date"]).tz_convert("Europe/Madrid")
            if m["status"] != "FullTime" or local.date().isoformat() >= "2026-10-02":
                pending += 1
                continue
            matches.append(
                {
                    "date": local.date().isoformat(),
                    "time": local.strftime("%H:%M"),
                    "round": str(raw["matchday"]),
                    "team1": m["home_team"],
                    "team2": m["away_team"],
                    "score": [m["home_score"], m["away_score"]],
                }
            )
        if not matches:
            continue
        frame = normalize_payload({"matches": matches}, raw["season"], code)
        frame["source"], frame["source_url"], frame["source_sha256"] = (
            "laliga_public_results",
            raw["source_url"],
            hashes[file.name],
        )
        frame["source_priority"], frame["gender"], frame["phase"] = 4, "men", "regular"
        frames.append(frame)
    new = pd.concat(frames, ignore_index=True)
    keys = ["competition_code", "season", "home_team", "away_team"]
    overlap = men.merge(new, on=keys, suffixes=("_old", "_new"))
    conflicts = overlap[
        (overlap.home_goals_old != overlap.home_goals_new)
        | (overlap.away_goals_old != overlap.away_goals_new)
        | (overlap.date_old != overlap.date_new)
    ]
    if len(conflicts):
        raise ValueError(
            f"Current source disagrees with archived results: {conflicts[keys].to_dict('records')}"
        )
    updated = (
        pd.concat([men, new], ignore_index=True)
        .sort_values("source_priority")
        .drop_duplicates(keys, keep="last")
    )
    validate_matches(updated)
    for code, group in updated[updated.season.eq("2026-27")].groupby("competition_code"):
        teams = set(group.home_team) | set(group.away_team)
        if len(teams) > (20 if code == "es.1" else 22):
            raise ValueError(f"Unexpected current-season roster for {code}: {sorted(teams)}")
    women = pd.read_parquet(women_path)
    combined = pd.concat([updated, women], ignore_index=True).sort_values(
        ["date", "competition_code", "home_team"]
    )
    output = ROOT / "data/processed/matches_quiniela_current.parquet"
    combined.to_parquet(output, index=False)
    seasons = []
    for (code, season), group in combined.groupby(["competition_code", "season"]):
        teams = len(set(group.home_team) | set(group.away_team))
        expected = (
            380
            if code == "es.1"
            else 462
            if code == "es.2"
            else 306
            if season == "2020-21"
            else 240
        )
        seasons.append(
            {
                "competition_code": code,
                "season": season,
                "matches": len(group),
                "teams": teams,
                "expected_matches": expected,
                "complete": len(group) == expected,
            }
        )
    audit = {
        "rows": len(combined),
        "as_of_exclusive": "2026-10-02",
        "seasons": seasons,
        "snapshot_hashes": hashes,
        "pending_source_rows": pending,
        "dataset_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "component_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (men_path, women_path)
        },
        "men_added": len(updated) - len(men),
        "source_conflicts": 0,
        "scope": "Current Primera, Segunda and Liga F; original evaluation datasets preserved",
    }
    output.with_suffix(".audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(
        {
            "rows": len(combined),
            "men_added": audit["men_added"],
            "last_dates": combined.groupby("competition_code").date.max().astype(str).to_dict(),
        }
    )


if __name__ == "__main__":
    main()
