"""Snapshot public LaLiga result pages, retaining only match records and provenance."""

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    root = ROOT / "data/raw/research_20260925/laliga"
    root.mkdir(parents=True, exist_ok=True)
    jobs = (
        [(2024, 42)]
        + [(2025, week) for week in range(1, 43)]
        + [(2026, week) for week in range(1, 8)]
    )

    def fetch(job):
        year, week = job
        path = root / f"{year}-es.2-{week:02}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        url = f"https://www.laliga.com/laliga-hypermotion/resultados/{year}-{str(year + 1)[-2:]}/jornada-{week}"
        response = requests.get(url, timeout=45)
        response.raise_for_status()
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', response.text)
        if not match:
            raise ValueError(f"Missing public page data: {url}")
        page = json.loads(match.group(1))["props"]["pageProps"]
        if int(page["season"]) != year or int(page["gameweek"]["week"]) != week:
            raise ValueError(f"Source returned the wrong season or round: {url}")
        rows = []
        for fixture in page["matches"]:
            rows.append(
                {
                    **{
                        k: fixture.get(k)
                        for k in ("id", "date", "home_score", "away_score", "status")
                    },
                    "home_team": fixture["home_team"]["nickname"],
                    "away_team": fixture["away_team"]["nickname"],
                    "home_team_id": fixture["home_team"]["id"],
                    "away_team_id": fixture["away_team"]["id"],
                }
            )
        record = {
            "source_url": url,
            "season": f"{year}-{str(year + 1)[-2:]}",
            "matchday": week,
            "fetched_at": datetime.now(UTC).isoformat(),
            "page_sha256": hashlib.sha256(response.content).hexdigest(),
            "matches": rows,
        }
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(path.name, len(rows), sum(m["status"] == "FullTime" for m in rows), flush=True)
        return record

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(fetch, jobs))


if __name__ == "__main__":
    main()
