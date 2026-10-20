"""Cache the current men's first eight rounds, including unplayed fixture statuses."""

import time
from pathlib import Path

from fetch_ligaf import fetch

ROOT = Path(__file__).resolve().parents[1]


def main():
    root = ROOT / "data/raw/current_20261002/laliga"
    root.mkdir(parents=True, exist_ok=True)
    for code in ("es.1", "es.2"):
        for week in range(1, 9):
            fetch(2026, week, root, code)
            time.sleep(0.25)


if __name__ == "__main__":
    main()
