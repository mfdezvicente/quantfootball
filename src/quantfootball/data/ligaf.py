"""Audited women's results, isolated from the existing men's dataset."""

import hashlib
import json
from pathlib import Path

import pandas as pd

from quantfootball.data.competitions import women_team_name


def build_ligaf_dataset(snapshot, output, as_of="2026-10-02"):
    snapshot, output = Path(snapshot), Path(output)
    boundary = pd.Timestamp(as_of)
    rows, hashes, names = [], {}, {}
    paths = sorted(snapshot.glob("*-es.w.1-*.json"))
    if not paths:
        raise ValueError("No Liga F snapshots found.")
    records = []
    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        if "/futbol-femenino/resultados/" not in raw["source_url"]:
            raise ValueError("Source is not a women's results page.")
        for m in raw["matches"]:
            for side in ("home", "away"):
                team_id = str(m[f"{side}_team_id"])
                name = women_team_name(m[f"{side}_team"])
                if team_id in names and names[team_id] != name:
                    raise ValueError(f"Review renamed women's team ID {team_id} before merging.")
                names[team_id] = name
            records.append((raw, m, hashes[path.name]))
    if len(set(names.values())) != len(names):
        raise ValueError("Women's source has different IDs with the same name; review identity.")
    pending = 0
    for raw, m, digest in records:
        kickoff = pd.Timestamp(m["date"])
        if pd.isna(kickoff) or kickoff.tz is None:
            raise ValueError("Source kickoff requires an explicit timezone.")
        local = kickoff.tz_convert("Europe/Madrid")
        date = local.tz_localize(None).normalize()
        if m["status"] != "FullTime" or date >= boundary:
            pending += 1
            continue
        goals = [m["home_score"], m["away_score"]]
        if any(isinstance(g, bool) or not isinstance(g, int) or g < 0 for g in goals):
            raise ValueError("Completed source scores must be nonnegative integers.")
        hg, ag = goals
        h, a = str(m["home_team_id"]), str(m["away_team_id"])
        if h == a:
            raise ValueError("Team plays itself.")
        rows.append(
            {
                "match_id": f"es.w.1:laliga:{m['id']}",
                "competition": "Liga F",
                "competition_code": "es.w.1",
                "country": "Spain",
                "season": raw["season"],
                "matchday": raw["matchday"],
                "date": date,
                "kickoff_time": local.strftime("%H:%M"),
                "home_team": names[h],
                "away_team": names[a],
                "home_team_id": f"women:laliga:{h}",
                "away_team_id": f"women:laliga:{a}",
                "home_team_raw": m["home_team"],
                "away_team_raw": m["away_team"],
                "home_goals": hg,
                "away_goals": ag,
                "home_goals_ht": None,
                "away_goals_ht": None,
                "result": "H" if hg > ag else "A" if hg < ag else "D",
                "is_completed": True,
                "source": "laliga_public_results",
                "source_url": raw["source_url"],
                "source_sha256": digest,
                "source_priority": 3,
                "gender": "women",
                "phase": "regular",
            }
        )
    data = pd.DataFrame(rows).sort_values(["date", "home_team"]).reset_index(drop=True)
    if (
        data.empty
        or data.match_id.duplicated().any()
        or data.duplicated(["season", "home_team_id", "away_team_id"]).any()
    ):
        raise ValueError("Empty dataset or duplicate women's fixture.")
    seasons = []
    for season, group in data.groupby("season"):
        n = 18 if season == "2020-21" else 16
        ids = set(group.home_team_id) | set(group.away_team_id)
        home_counts, away_counts = (
            group.home_team_id.value_counts(),
            group.away_team_id.value_counts(),
        )
        complete = (
            len(group) == n * (n - 1)
            and len(ids) == n
            and home_counts.eq(n - 1).all()
            and away_counts.eq(n - 1).all()
        )
        record = {
            "competition_code": "es.w.1",
            "season": season,
            "matches": len(group),
            "expected_matches": n * (n - 1),
            "teams": len(ids),
            "complete": bool(complete),
            "last_date": group.date.max().date().isoformat(),
        }
        if pd.Timestamp(f"{int(season[:4]) + 1}-08-15") < boundary and not complete:
            raise ValueError(f"Incomplete closed women's season: {record}")
        seasons.append(record)
    output.parent.mkdir(parents=True, exist_ok=True)
    data.to_parquet(output, index=False)
    audit = {
        "rows": len(data),
        "as_of_exclusive": as_of,
        "seasons": seasons,
        "dataset_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "snapshot_hashes": hashes,
        "pending_source_rows": pending,
        "team_ids": names,
        "scope": "Women's Spanish top division only, isolated by gender and source team ID",
        "source_availability": "Retrieved now; revised historical pages do not prove pre-match availability",
    }
    output.with_suffix(".audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return audit
