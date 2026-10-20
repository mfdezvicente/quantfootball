"""Merge FullTime public results into a new dated dataset without live scores."""

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import pandas as pd

from quantfootball.data.competitions import GENDERS, validate_competitions, women_team_name
from quantfootball.data.openfootball import normalize_payload, validate_matches


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def update_snapshot(base, snapshots, output, as_of):
    """Accept only final results strictly before the Madrid calendar cutoff."""
    base, output = Path(base), Path(output)
    audit_path = output.with_suffix(".audit.json")
    if output.exists() or audit_path.exists():
        raise ValueError("Choose a new output path; historical snapshots are immutable.")
    boundary = pd.Timestamp(as_of)
    if (pd.isna(boundary) or boundary.tz is not None or boundary != boundary.normalize()
            or boundary.date() > datetime.now(ZoneInfo("Europe/Madrid")).date()):
        raise ValueError("Use a calendar cutoff no later than today in Madrid.")
    history = pd.read_parquet(base)
    validate_competitions(history)
    validate_matches(history)
    if pd.to_datetime(history.date).max() >= boundary:
        raise ValueError("Base history already reaches the requested exclusive cutoff.")
    women_ids = {}
    for row in history[history.competition_code.eq("es.w.1")].to_dict("records"):
        for side in ("home", "away"):
            identity = row.get(f"{side}_team_id")
            if pd.notna(identity):
                name = row[f"{side}_team"]
                if identity in women_ids and women_ids[identity] != name:
                    raise ValueError("Inconsistent archived women's team identity.")
                women_ids[identity] = name
    paths = sorted({p.resolve() for folder in snapshots for p in Path(folder).glob("*-es.*-*.json")})
    if not paths:
        raise ValueError("No public league snapshot files found.")
    frames, hashes, skipped, observed = [], {}, [], 0
    slugs = {"es.1": "laliga-easports", "es.2": "laliga-hypermotion", "es.w.1": "futbol-femenino"}
    seasons = set()
    for path in paths:
        parsed = re.fullmatch(r"(\d{4})-(es\.1|es\.2|es\.w\.1)-(\d{2})\.json", path.name)
        if not parsed:
            raise ValueError(f"Unexpected league snapshot name: {path.name}")
        year, code, week = parsed.groups()
        raw = json.loads(path.read_text(encoding="utf-8"))
        season = f"{year}-{str(int(year) + 1)[-2:]}"
        seasons.add(season)
        source = urlsplit(raw["source_url"])
        captured = datetime.fromisoformat(raw["fetched_at"])
        if (source.scheme != "https" or source.hostname != "www.laliga.com"
                or source.path != f"/{slugs[code]}/resultados/{season}/jornada-{int(week)}"
                or raw["season"] != season or raw["matchday"] != int(week)
                or captured.tzinfo is None or captured > datetime.now(UTC)):
            raise ValueError("Inconsistent source URL, season, round or capture time.")
        sha = hashes[str(path)] = digest(path)
        men, women = [], []
        for match in raw["matches"]:
            observed += 1
            kickoff = pd.Timestamp(match["date"])
            if pd.isna(kickoff) or kickoff.tz is None:
                raise ValueError("Source kickoff requires an explicit timezone.")
            local = kickoff.tz_convert("Europe/Madrid")
            date = local.tz_localize(None).normalize()
            if match["status"] != "FullTime" or date >= boundary:
                skipped.append({"competition_code": code, "match_id": match["id"],
                                "home_team": match["home_team"], "away_team": match["away_team"],
                                "date": date.date().isoformat(), "status": match["status"],
                                "reason": "not_full_time" if match["status"] != "FullTime" else "at_or_after_cutoff"})
                continue
            goals = [match["home_score"], match["away_score"]]
            if any(isinstance(g, bool) or not isinstance(g, int) or g < 0 for g in goals):
                raise ValueError("Final scores must be nonnegative integers.")
            if code != "es.w.1":
                men.append({"date": date.date().isoformat(), "time": local.strftime("%H:%M"),
                            "round": week, "team1": match["home_team"], "team2": match["away_team"], "score": goals})
                continue
            ids, names = [], []
            for side in ("home", "away"):
                identity = f"women:laliga:{match[f'{side}_team_id']}"
                name = women_team_name(match[f"{side}_team"])
                if identity in women_ids and women_ids[identity] != name:
                    raise ValueError(f"Review renamed women's team: {identity}")
                if any(other_id != identity and other_name == name for other_id, other_name in women_ids.items()):
                    raise ValueError(f"Different women's IDs share a canonical name: {name}")
                women_ids[identity] = name
                ids.append(identity)
                names.append(name)
            if ids[0] == ids[1] or names[0] == names[1]:
                raise ValueError("Women's team plays itself.")
            hg, ag = goals
            women.append({"match_id": f"es.w.1:laliga:{match['id']}", "competition": "Liga F",
                          "competition_code": code, "country": "Spain", "season": season,
                          "matchday": raw["matchday"], "date": date, "kickoff_time": local.strftime("%H:%M"),
                          "home_team": names[0], "away_team": names[1], "home_team_id": ids[0], "away_team_id": ids[1],
                          "home_team_raw": match["home_team"], "away_team_raw": match["away_team"],
                          "home_goals": hg, "away_goals": ag, "home_goals_ht": None, "away_goals_ht": None,
                          "result": "H" if hg > ag else "A" if hg < ag else "D", "is_completed": True})
        frame = pd.DataFrame(women) if code == "es.w.1" else normalize_payload({"matches": men}, season, code)
        if frame.empty:
            continue
        for name, value in {"source": "laliga_public_results", "source_url": raw["source_url"],
                            "source_sha256": sha, "source_priority": 4, "gender": GENDERS[code], "phase": "regular"}.items():
            frame[name] = value
        frames.append(frame)
    keys = ["competition_code", "season", "home_team", "away_team"]
    new = pd.concat(frames, ignore_index=True) if frames else history.iloc[:0].copy()
    if new.duplicated(keys).any():
        raise ValueError("Overlapping source snapshots; select one capture per fixture.")
    overlap = history.merge(new, on=keys, suffixes=("_old", "_new"))
    for field in ("date", "home_goals", "away_goals"):
        if not overlap[f"{field}_old"].eq(overlap[f"{field}_new"]).all():
            raise ValueError(f"Source conflicts with archived {field}; review before merging.")
    existing = set(history[keys].itertuples(index=False, name=None))
    added = new.loc[[k not in existing for k in new[keys].itertuples(index=False, name=None)]]
    combined = pd.concat([history, added], ignore_index=True).sort_values(
        ["date", "competition_code", "home_team"]).reset_index(drop=True)
    validate_competitions(combined)
    validate_matches(combined)
    if combined.duplicated(keys).any():
        raise ValueError("Duplicate competition/season fixture after merging.")
    for (code, _season), group in combined[combined.season.isin(seasons)].groupby(["competition_code", "season"]):
        expected = 18 if code == "es.w.1" and _season == "2020-21" else {"es.1": 20, "es.2": 22, "es.w.1": 16}[code]
        if len(set(group.home_team) | set(group.away_team)) > expected:
            raise ValueError(f"Unexpected season roster: {code}/{_season}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        combined.to_parquet(handle, index=False)
    audit = {"created_at": datetime.now(UTC).isoformat(), "rows": len(combined), "as_of_exclusive": as_of,
             "dataset_sha256": digest(output), "base_path": str(base.resolve()), "base_sha256": digest(base),
             "snapshot_sha256": hashes, "observed_source_rows": observed, "added_rows": len(added),
             "added_by_competition": added.competition_code.value_counts().to_dict(),
             "last_dates": combined.groupby("competition_code").date.max().astype(str).to_dict(),
             "skipped_source_rows": skipped, "source_conflicts": 0,
             "policy": "Only FullTime results strictly before cutoff; original rows preserved; live scores excluded"}
    with audit_path.open("x", encoding="utf-8") as handle:
        json.dump(audit, handle, ensure_ascii=False, indent=2, allow_nan=False)
    return audit
