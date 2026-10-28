"""Deprecated alias of refresh_dataset.py; requires explicit immutable inputs/output."""

import sys

from refresh_dataset import main as refresh_main


def main():
    print(
        "Deprecated entry point: use scripts/refresh_dataset.py. "
        "Explicit --base, --snapshot, --as-of and --output are required; "
        "existing snapshots are never overwritten.",
        file=sys.stderr,
    )
    refresh_main()


if __name__ == "__main__":
    main()
