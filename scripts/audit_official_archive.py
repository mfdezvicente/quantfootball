"""Report every Sunday in the requested window before running model/ROI experiments."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from quantfootball.quiniela.settlement import match_coupon, parse_official_extract

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data/raw/official_expanded")
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()
    data = pd.read_parquet(ROOT / "data/processed/matches_spain.parquet")
    exceptions = json.loads(
        (ROOT / "configs/settlement_exceptions.json").read_text(encoding="utf-8")
    )
    rows = []
    for date in pd.date_range("2024-08-04", "2026-06-07", freq="W-SUN"):
        key = date.date().isoformat()
        paths = sorted(a.raw_dir.glob(f"{key}*.txt"))
        text = "\n".join(p.read_text(encoding="utf-8") for p in paths)
        row = {
            "date": key,
            "files": [p.name for p in paths],
            "sources_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        }
        if key in exceptions:
            row["settlement_exception"] = exceptions[key]
        try:
            coupon = parse_official_extract(text, key)
            row["prizes_complete"] = len(coupon["prizes"]) == 6
            row["source_teams"] = [
                f["home_raw"] + " / " + f["away_raw"] for f in coupon["fixtures"]
            ]
            frame, pleno = match_coupon(coupon, data)
            row["status"] = "eligible" if row["prizes_complete"] else "missing_prizes"
            row["cutoff"] = min(frame.date.min(), pleno["date"]).date().isoformat()
        except ValueError as exc:
            row["status"] = "excluded"
            row["reason"] = str(exc)
        rows.append(row)
    report = {
        "scope": ["2024-08-04", "2026-06-07"],
        "rows": rows,
        "counts": dict(Counter(r["status"] for r in rows)),
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report["counts"])
    for row in rows:
        if row["status"] != "eligible":
            print(row["date"], row["status"], row.get("reason", ""))


if __name__ == "__main__":
    main()
