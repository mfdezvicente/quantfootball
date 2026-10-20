"""Cache public Liga F result pages with provenance and strict season checks."""

import argparse
import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def fetch(year, week, root, code="es.w.1"):
    slugs = {"es.w.1": "futbol-femenino", "es.1": "laliga-easports", "es.2": "laliga-hypermotion"}
    path = root / f"{year}-{code}-{week:02}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    url = f"https://www.laliga.com/{slugs[code]}/resultados/{year}-{str(year + 1)[-2:]}/jornada-{week}"
    for attempt in range(3):
        response = requests.get(url, timeout=45)
        if response.status_code not in (500, 502, 503, 504):
            break
        time.sleep(2 * (attempt + 1))
    response.raise_for_status()
    embedded = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', response.text)
    if not embedded:
        raise ValueError(f"Missing public page data: {url}")
    page = json.loads(embedded.group(1))["props"]["pageProps"]
    if int(page["season"]) != year or int(page["gameweek"]["week"]) != week:
        raise ValueError(f"Source returned a different season/round: {url}")
    rows = []
    for m in page["matches"]:
        rows.append(
            {
                **{k: m.get(k) for k in ("id", "date", "home_score", "away_score", "status")},
                "home_team": m["home_team"]["nickname"],
                "away_team": m["away_team"]["nickname"],
                "home_team_id": m["home_team"]["id"],
                "away_team_id": m["away_team"]["id"],
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start-year", type=int, default=2020)
    p.add_argument("--end-year", type=int, default=2026)
    p.add_argument("--probe", action="store_true")
    p.add_argument("--output-dir", type=Path, default=ROOT / "data/raw/ligaf_20261002")
    a = p.parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    for year in range(a.start_year, a.end_year + 1):
        # 2020/21 had 18 clubs. All later seasons use 16 clubs.
        rounds = 34 if year == 2020 else 30
        for week in [1] if a.probe else range(1, (5 if year == 2026 else rounds) + 1):
            fetch(year, week, a.output_dir)
            time.sleep(0.25)


if __name__ == "__main__":
    main()
