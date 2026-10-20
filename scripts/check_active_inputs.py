"""Read-only operational preflight. Does not fetch odds or register predictions."""

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from quantfootball.data.active import inspect_inputs, resolve_active

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    try:
        active = resolve_active(ROOT, args.manifest)
        report = inspect_inputs(active["dataset"], active["config"],
                                datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat(),
                                active["max_result_age_days"])
        report["manifest_sha256"] = active["manifest_sha256"]
    except (ValueError, OSError, KeyError, TypeError) as exc:
        report = {"ready": False, "errors": [str(exc)]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ready"] else 2)


if __name__ == "__main__":
    main()
