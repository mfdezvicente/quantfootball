"""Collect current EU three-way odds, using at most two expected credits per run."""

import argparse
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from quantfootball.market.credentials import credential_status, load_api_key
from quantfootball.market.odds_api import SPORT_KEYS, OddsAPIClient, OddsAPIError, convert_records
from quantfootball.market.snapshots import instant

ROOT = Path(__file__).resolve().parents[1]


def write_new(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Local status; no network or credit use")
    mode.add_argument("--check", action="store_true", help="Provider catalogue and quota; no odds credits")
    parser.add_argument("--competitions", nargs="+", choices=sorted(SPORT_KEYS), default=sorted(SPORT_KEYS))
    parser.add_argument("--from-time", help="Aware ISO kickoff boundary; default is actual current UTC")
    parser.add_argument("--to-time", help="Aware ISO kickoff boundary; default is seven days from start")
    parser.add_argument("--aliases", type=Path, help="Reviewed JSON provider name -> canonical team aliases")
    parser.add_argument("--output-dir", type=Path, help="New immutable folder; default data/raw/market_the_odds_api/UTC")
    args = parser.parse_args()
    if args.status:
        print(json.dumps(credential_status(ROOT), indent=2, ensure_ascii=False))
        return
    codes = list(dict.fromkeys(args.competitions))
    start = instant(args.from_time) if args.from_time else datetime.now(UTC)
    end = instant(args.to_time) if args.to_time else start + timedelta(days=7)
    if not start < end or end - start > timedelta(days=14):
        parser.error("La ventana debe ser positiva y no superar catorce días.")
    if args.output_dir and args.output_dir.exists():
        parser.error("Elige una carpeta nueva para conservar las capturas anteriores.")
    aliases = json.loads(args.aliases.read_text(encoding="utf-8-sig")) if args.aliases else {}
    if not isinstance(aliases, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                          or not k.strip() or not v.strip() for k, v in aliases.items()):
        parser.error("Archivo de alias no válido.")
    try:
        client = OddsAPIClient(load_api_key(ROOT))
        catalogue, catalog_metadata = client.sports()
    except (ValueError, OddsAPIError) as exc:
        parser.exit(2, str(exc) + "\n")
    available = {sport["key"]: sport for sport in catalogue}
    coverage = {code: {"sport_key": SPORT_KEYS[code], "listed": SPORT_KEYS[code] in available,
                       "active": bool(available.get(SPORT_KEYS[code], {}).get("active"))}
                for code in codes}
    if args.check:
        print(json.dumps({"provider": "the_odds_api_v4", "catalogue_request": catalog_metadata,
            "coverage": coverage, "liga_f": "Not configured; inspect the current provider catalogue",
            "catalogue": catalogue}, indent=2, ensure_ascii=False))
        return
    remaining = catalog_metadata["quota"].get("x-requests-remaining")
    if remaining is None or remaining < len(codes):
        parser.exit(2, "No se puede confirmar cuota suficiente. No se han solicitado cuotas.\n")
    output = args.output_dir or ROOT / "data/raw/market_the_odds_api" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=False)
    records, errors = [], []
    attempted, credit_cost = 0, 0
    for code in codes:
        if not coverage[code]["listed"] or not coverage[code]["active"]:
            errors.append({"competition_code": code, "reason": "not_listed_or_inactive"})
            continue
        if remaining < 1:
            errors.append({"competition_code": code, "reason": "no_quota_remaining"})
            break
        attempted += 1
        try:
            record = client.current_odds(code, start.isoformat(), end.isoformat())
        except OddsAPIError as exc:
            errors.append({"competition_code": code, "reason": str(exc)})
            # No retry: a failed request may have consumed a credit.
            break
        records.append(record)
        write_new(output / f"{code}.json", record)
        used = record["quota"].get("x-requests-last")
        remaining = record["quota"].get("x-requests-remaining", 0)
        if used is None:
            errors.append({"competition_code": code, "reason": "quota_cost_unavailable_no_more_requests"})
            break
        credit_cost += used
        if used > 1 or credit_cost > 2:
            errors.append({"competition_code": code, "reason": "unexpected_credit_cost_no_more_requests"})
            break
    snapshot = None
    if records:
        try:
            snapshot = convert_records(records, aliases=aliases)
            write_new(output / "snapshot.json", snapshot)
        except (ValueError, TypeError, KeyError) as exc:
            # Provider payloads are credential-redacted before validation and saving.
            errors.append({"reason": "snapshot_conversion_failed", "detail": str(exc)})
    write_new(output / "audit.json", {
        "schema_version": 1, "created_at": datetime.now(UTC).isoformat(),
        "provider": "the_odds_api_v4", "catalogue": catalogue,
        "catalogue_request": catalog_metadata, "coverage": coverage, "aliases": aliases,
        "expected_credit_limit_per_run": 2, "attempted_odds_requests": attempted,
        "reported_credit_cost_successful_requests": credit_cost, "remaining_after_last_success": remaining,
        "errors": errors, "fixture_count": len(snapshot["fixtures"]) if snapshot else 0,
        "files_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(output.glob("*.json"))},
        "limitations": ["Free subscription has no historical odds endpoint",
                        "Only configured men's competitions are requested",
                        "No crowd betting shares, expected prize or ROI are inferred"]})
    print(f"Captura: {output}; partidos con cuotas válidas: {len(snapshot['fixtures']) if snapshot else 0}; avisos: {len(errors)}.")
    if not snapshot or not snapshot["fixtures"]:
        parser.exit(2, "No hay cuotas utilizables; consulta audit.json.\n")


if __name__ == "__main__":
    main()
