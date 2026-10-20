"""Capture specified public LaLiga rounds in a new local snapshot directory."""

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from fetch_ligaf import fetch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--competition", required=True, choices=("es.1", "es.2", "es.w.1"))
    parser.add_argument("--year", required=True, type=int, help="Season start year, e.g. 2026 for 2026/27")
    parser.add_argument("--matchday", required=True, action="append", type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    max_week = {"es.1": 38, "es.2": 42, "es.w.1": 34 if args.year == 2020 else 30}[args.competition]
    if not 1990 <= args.year <= datetime.now(ZoneInfo("Europe/Madrid")).year:
        parser.error("Season start year must be between 1990 and the current year.")
    weeks = sorted(set(args.matchday))
    if any(not 1 <= week <= max_week for week in weeks):
        parser.error("Matchday is outside the competition's regular season.")
    paths = [args.output_dir / f"{args.year}-{args.competition}-{week:02}.json" for week in weeks]
    if any(path.exists() for path in paths):
        parser.error("A snapshot already exists; select a new capture directory to preserve provenance.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        for week in weeks:
            fetch(args.year, week, args.output_dir, args.competition)
    except (requests.RequestException, ValueError, KeyError, OSError) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    main()
