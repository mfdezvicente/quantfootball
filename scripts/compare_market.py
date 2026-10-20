"""Compare a frozen forecast with an authorized, timestamped JSON odds snapshot."""

import argparse
import hashlib
import json
from pathlib import Path

from quantfootball.market.snapshots import compare_snapshot
from quantfootball.quiniela.dashboard import render_dashboard


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forecast", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--decision-at", required=True)
    parser.add_argument("--max-age-hours", type=float, default=48)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("Choose a new output directory.")
    report = json.loads(args.forecast.read_text(encoding="utf-8"))
    if len(report["coupons"]) != 1:
        parser.error("Supply one forecast coupon, not a retrospective archive.")
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    comparison = compare_snapshot(
        report["coupons"][0], snapshot, args.decision_at, max_age_hours=args.max_age_hours
    )
    comparison["inputs_sha256"] = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in [("forecast", args.forecast), ("snapshot", args.snapshot)]
    }
    report["coupons"][0]["market_comparison"] = comparison
    args.output_dir.mkdir(parents=True)
    for name, value in [("comparison.json", comparison), ("forecast.json", report)]:
        with (args.output_dir / name).open("x", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
    render_dashboard(report, {}, {}, args.output_dir / "dashboard.html")
    print(f"Matched {comparison['matched_fixtures']}/14 fixtures; no expected ROI calculated.")


if __name__ == "__main__":
    main()
