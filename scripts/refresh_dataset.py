"""Create an immutable updated mixed-league dataset from public result snapshots."""

import argparse
import json
from pathlib import Path

from quantfootball.data.current import update_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, action="append", required=True)
    parser.add_argument("--as-of", required=True, help="Exclusive Madrid calendar cutoff")
    parser.add_argument("--output", type=Path, required=True, help="New parquet; preserve previous snapshots")
    args = parser.parse_args()
    try:
        audit = update_snapshot(args.base, args.snapshot, args.output, args.as_of)
    except (ValueError, KeyError, OSError, TypeError) as exc:
        parser.exit(2, str(exc) + "\n")
    print(json.dumps({k: audit[k] for k in ("rows", "added_rows", "added_by_competition", "last_dates")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
