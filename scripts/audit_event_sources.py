"""Audit recent Spanish open-event coverage before using xG features."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    root = ROOT / "data/raw/event_source_audit_20261002"
    root.mkdir(parents=True, exist_ok=False)
    response = requests.get(
        "https://api.github.com/repos/hudl/open-data/commits/master", timeout=45
    )
    response.raise_for_status()
    commit = response.json()["sha"]
    provenance = {}

    def get(relative):
        url = f"https://raw.githubusercontent.com/hudl/open-data/{commit}/{relative}"
        r = requests.get(url, timeout=45)
        r.raise_for_status()
        name = relative.replace("/", "_")
        (root / name).write_bytes(r.content)
        provenance[relative] = {"url": url, "sha256": hashlib.sha256(r.content).hexdigest()}
        return r

    get("README.md")
    get("LICENSE.pdf")
    competitions = get("data/competitions.json").json()
    summaries = []
    for c in competitions:
        if c["country_name"] != "Spain" or c["competition_name"] not in ("La Liga", "Liga F"):
            continue
        year = int(c["season_name"][:4])
        if year < 2021:
            continue
        games = get(f"data/matches/{c['competition_id']}/{c['season_id']}.json").json()
        teams = {m[s][f"{s}_name"] for m in games for s in ("home_team", "away_team")}
        summaries.append(
            {
                "competition": c["competition_name"],
                "gender": c["competition_gender"],
                "season": c["season_name"],
                "matches": len(games),
                "teams": len(teams),
                "first_date": min(m["match_date"] for m in games),
                "last_date": max(m["match_date"] for m in games),
                "expected_matches": 240 if c["competition_name"] == "Liga F" else 380,
                "available_updated": c["match_available"],
            }
        )
    report = {
        "commit": commit,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "recent_spain_coverage": summaries,
        "files": provenance,
        "decision": "Metadata and licence only; events not added to predictors without sufficient representative time coverage",
    }
    (root / "audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"commit": commit, "recent_spain_coverage": summaries}, indent=2))


if __name__ == "__main__":
    main()
