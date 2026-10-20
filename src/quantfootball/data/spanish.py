"""Build an audited men's Primera/Segunda dataset from versioned source snapshots."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

from quantfootball.data.openfootball import normalize_payload, validate_matches

MONTHS = {
    name: i
    for i, name in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1
    )
}


def parse_football_txt(text: str, season: str) -> dict:
    """Parse observed level-1/2 results; fail loudly on an unrecognized match line."""
    year = int(season[:4])
    current_date, kickoff, round_name = None, None, None
    matches = []
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", "=", ">", "~")):
            continue
        if line.startswith("▪"):
            round_name = line[1:].strip()
            continue
        day = re.match(
            r"^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\w{3})\s+(\d{1,2})(?:\s+(\d{4}))?", line
        )
        if day:
            month = MONTHS[day[1]]
            y = int(day[3]) if day[3] else year + (month < 7)
            current_date, kickoff = date(y, month, int(day[2])).isoformat(), None
            continue
        time = re.match(r"^(\d{1,2}:\d{2})\s+", line)
        if time:
            kickoff, line = time[1], line[time.end() :]
        if not current_date or not round_name:
            raise ValueError(f"Match without date/round at line {line_number}: {line}")
        score = None
        if " v " in line:
            home, rest = line.split(" v ", 1)
            ending = re.search(r"\s+(\d+)-(\d+)(?:\s+\(\d+-\d+\))?\s*$", rest)
            if ending:
                away, score = rest[: ending.start()].strip(), [int(ending[1]), int(ending[2])]
            else:
                away = rest.strip()
        else:
            middle = re.match(r"^(.+?)\s+(\d+)-(\d+)(?:\s+\(\d+-\d+\))?\s+(.+?)$", line)
            if not middle:
                raise ValueError(f"Unrecognized football line {line_number}: {line}")
            home, away, score = middle[1], middle[4], [int(middle[2]), int(middle[3])]
        matches.append(
            {
                "round": round_name,
                "date": current_date,
                "time": kickoff,
                "team1": home.strip(),
                "team2": away.strip(),
                "score": {"ft": score},
            }
        )
    return {"matches": matches}


def build_spanish_dataset(snapshot: Path, output: Path, *, as_of: str = "2026-09-25") -> dict:
    frames = []
    snapshot_hashes = {}
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    records = {r["path"].replace("\\", "/"): r for r in manifest["files"]}
    txt_manifest = json.loads((snapshot / "espana_manifest.json").read_text(encoding="utf-8"))
    records.update({r["path"].replace("\\", "/"): r for r in txt_manifest["files"]})

    def add(payload, season, code, source, url, sha, priority):
        frame = normalize_payload(payload, season, code)
        frame["source"], frame["source_url"], frame["source_sha256"] = source, url, sha
        frame["source_priority"] = priority
        frame["gender"], frame["phase"] = "men", "regular"
        frames.append(frame)

    for path in sorted((snapshot / "openfootball").glob("*/*.json")):
        record = records[path.relative_to(snapshot).as_posix()]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != record["sha256"]:
            raise ValueError(f"Snapshot hash mismatch: {path}")
        snapshot_hashes[path.relative_to(snapshot).as_posix()] = digest
        add(
            json.loads(path.read_text(encoding="utf-8")),
            path.parent.name,
            path.stem,
            "openfootball_json",
            record["url"],
            record["sha256"],
            1,
        )
    for path in sorted((snapshot / "espana").glob("*/*.txt")):
        # Only needed upstream supplements; other TXT files use richer scorer syntax.
        if not (
            path.name == "2-liga2.txt"
            and path.parent.name in {"2021-22", "2022-23", "2023-24", "2024-25"}
            or path.name == "1-liga.txt"
            and path.parent.name == "2024-25"
        ):
            continue
        record = records[path.relative_to(snapshot).as_posix()]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != record["sha256"]:
            raise ValueError(f"Snapshot hash mismatch: {path}")
        snapshot_hashes[path.relative_to(snapshot).as_posix()] = digest
        code = "es.1" if path.name.startswith("1-") else "es.2"
        add(
            parse_football_txt(path.read_text(encoding="utf-8"), path.parent.name),
            path.parent.name,
            code,
            "openfootball_txt",
            record["url"],
            record["sha256"],
            2,
        )
    for path in sorted((snapshot / "laliga").glob("*-es.2-*.json")):
        snapshot_hashes[path.relative_to(snapshot).as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        data = json.loads(path.read_text(encoding="utf-8"))
        matches = []
        for m in data["matches"]:
            local = pd.Timestamp(m["date"]).tz_convert("Europe/Madrid")
            score = [m["home_score"], m["away_score"]] if m["status"] == "FullTime" else None
            matches.append(
                {
                    "date": local.date().isoformat(),
                    "time": local.strftime("%H:%M"),
                    "round": str(data["matchday"]),
                    "team1": m["home_team"],
                    "team2": m["away_team"],
                    "score": {"ft": score},
                }
            )
        add(
            {"matches": matches},
            data["season"],
            "es.2",
            "laliga_public_results",
            data["source_url"],
            data["page_sha256"],
            3,
        )
    all_rows = pd.concat(frames, ignore_index=True)
    keys = ["competition_code", "season", "home_team", "away_team"]
    completed = all_rows.loc[
        all_rows["is_completed"] & (all_rows["date"] < pd.Timestamp(as_of))
    ].copy()
    # Prefer official source, then upstream TXT; preserve conflicting results for review.
    conflicts, date_conflicts = [], []
    for key, group in completed.groupby(keys):
        if group["date"].nunique() > 1:
            date_conflicts.append(
                {
                    "fixture": list(key),
                    "alternatives": group[["date", "source"]].astype(str).to_dict("records"),
                }
            )
        if len(group[["home_goals", "away_goals"]].drop_duplicates()) > 1:
            conflicts.append(
                {
                    "fixture": list(key),
                    "alternatives": group[["date", "home_goals", "away_goals", "source"]]
                    .astype(str)
                    .to_dict("records"),
                }
            )
    completed = completed.sort_values("source_priority").drop_duplicates(keys, keep="last")
    completed = completed.sort_values(["date", "competition_code", "home_team"]).reset_index(
        drop=True
    )
    validate_matches(completed)
    audit = []
    for (code, season), group in completed.groupby(["competition_code", "season"]):
        expected = 380 if code == "es.1" else 462
        teams = set(group["home_team"]) | set(group["away_team"])
        audit.append(
            {
                "competition_code": code,
                "season": season,
                "matches": len(group),
                "teams": len(teams),
                "expected_matches": expected,
                "complete": len(group) == expected and len(teams) == (20 if code == "es.1" else 22),
                "last_date": group["date"].max().date().isoformat(),
            }
        )
    pending = all_rows.loc[~all_rows["is_completed"] | (all_rows["date"] >= pd.Timestamp(as_of))]
    if conflicts:
        raise ValueError(f"Unreviewed source score conflicts: {conflicts}")
    for row in audit:
        closed = pd.Timestamp(f"{int(row['season'][:4]) + 1}-08-15") < pd.Timestamp(as_of)
        if closed and not row["complete"]:
            raise ValueError(f"Incomplete closed season: {row}")
    output.parent.mkdir(parents=True, exist_ok=True)
    completed.to_parquet(output, index=False)
    report = {
        "as_of_exclusive": as_of,
        "rows": len(completed),
        "seasons": audit,
        "conflicts": conflicts,
        "date_conflicts": date_conflicts,
        "snapshot_hashes": snapshot_hashes,
        "source_priority": ["laliga_public_results", "openfootball_txt", "openfootball_json"],
        "dataset_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "pending_source_rows": len(pending),
        "provenance": "Pinned OpenFootball snapshots plus official LaLiga public result pages",
        "scope": "Men's Primera and Segunda regular season only; no playoffs or women's matches",
    }
    output.with_suffix(".audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
