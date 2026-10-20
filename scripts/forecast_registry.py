"""Register paper forecasts before the official deadline, verify, or settle later."""

import argparse
import json
from pathlib import Path

from quantfootball.quiniela.registry import (
    register_forecast,
    registry_summary,
    settle_record,
    verify_record,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register")
    register.add_argument("--forecast", type=Path, required=True)
    register.add_argument("--manifest", type=Path, required=True)
    register.add_argument("--root", type=Path, default=Path("outputs/predictions/registry"))
    verify = sub.add_parser("verify")
    verify.add_argument("--record", type=Path, required=True)
    settle = sub.add_parser("settle")
    settle.add_argument("--record", type=Path, required=True)
    settle.add_argument("--extract", type=Path, required=True)
    settle.add_argument("--source-url", required=True)
    summary = sub.add_parser("summary")
    summary.add_argument("--root", type=Path, default=Path("outputs/predictions/registry"))
    args = parser.parse_args()
    if args.command == "register":
        result = register_forecast(args.forecast, args.manifest, args.root)
    elif args.command == "verify":
        result = verify_record(args.record)
    elif args.command == "summary":
        result = registry_summary(args.root)
    else:
        result = settle_record(args.record, args.extract, args.source_url)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
