"""Build separate Liga F and combined mixed-coupon datasets without altering men's data."""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from quantfootball.data.ligaf import build_ligaf_dataset

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", type=Path, default=ROOT / "data/raw/ligaf_20261002")
    p.add_argument("--output", type=Path, default=ROOT / "data/processed/matches_ligaf.parquet")
    p.add_argument(
        "--combined", type=Path, default=ROOT / "data/processed/matches_quiniela.parquet"
    )
    p.add_argument("--as-of", default="2026-10-02")
    a = p.parse_args()
    audit = build_ligaf_dataset(a.snapshot, a.output, a.as_of)
    men_path = ROOT / "data/processed/matches_spain.parquet"
    men_audit = json.loads(men_path.with_suffix(".audit.json").read_text(encoding="utf-8"))
    combined = pd.concat([pd.read_parquet(men_path), pd.read_parquet(a.output)], ignore_index=True)
    combined.to_parquet(a.combined, index=False)
    combined_audit = {
        "rows": len(combined),
        "seasons": men_audit["seasons"] + audit["seasons"],
        "dataset_sha256": hashlib.sha256(a.combined.read_bytes()).hexdigest(),
        "as_of_exclusive": a.as_of,
        "component_cutoffs": {"men": men_audit["as_of_exclusive"], "women": a.as_of},
        "scope": "Separate Primera, Segunda and Liga F identities; men's archive is older",
    }
    a.combined.with_suffix(".audit.json").write_text(
        json.dumps(combined_audit, indent=2), encoding="utf-8"
    )
    print(json.dumps({"rows": audit["rows"], "seasons": audit["seasons"]}, indent=2))


if __name__ == "__main__":
    main()
