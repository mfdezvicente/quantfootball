"""Resolve explicit active inputs and fail closed on integrity/freshness errors."""

import hashlib
import json
from pathlib import Path

import pandas as pd

from quantfootball.data.competitions import validate_competitions
from quantfootball.data.openfootball import validate_matches

SCOPE = {"es.1", "es.2", "es.w.1"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve_active(root, manifest=None):
    root = Path(root).resolve()
    path = Path(manifest) if manifest else root / "configs/active_inputs.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("schema_version") != 1 or set(spec["competitions"]) != SCOPE:
        raise ValueError("Invalid active manifest schema or competition scope.")
    resolved = {}
    for name in ("dataset", "config", "audit"):
        entry = spec[name]
        target = (root / entry["path"]).resolve()
        if not target.is_relative_to(root) or sha256(target) != entry["sha256"]:
            raise ValueError(f"Active {name} is outside the repository or its hash changed.")
        resolved[name] = target
    audit = json.loads(resolved["audit"].read_text(encoding="utf-8"))
    if audit["dataset_sha256"] != spec["dataset"]["sha256"]:
        raise ValueError("Dataset audit does not match the active snapshot.")
    limit = spec["max_result_age_days"]
    if type(limit) is not int or not 1 <= limit <= 31:
        raise ValueError("Invalid operational freshness limit.")
    return resolved | {"manifest": path, "manifest_sha256": sha256(path),
                       "max_result_age_days": limit}


def inspect_inputs(dataset, config, cutoff, max_age_days=14, required=None):
    """Operational recency check, not proof of completeness or historical availability.

    Dates on/after cutoff are excluded from the inspection, as in training.
    Explicit historical runs may pass max_age_days=None.
    """
    required = set(required or SCOPE)
    if not required <= SCOPE:
        raise ValueError("Unsupported requested competition.")
    boundary = pd.Timestamp(cutoff)
    if pd.isna(boundary) or boundary.tz is not None or boundary != boundary.normalize():
        raise ValueError("Cutoff must be a timezone-free calendar date.")
    data = pd.read_parquet(dataset)
    validate_competitions(data)
    validate_matches(data)
    settings = json.loads(Path(config).read_text(encoding="utf-8"))
    dates = pd.to_datetime(data.date)
    history = data.loc[dates < boundary].copy()
    latest = history.groupby("competition_code").date.max()
    errors, leagues = [], {}
    for code in sorted(required):
        if code not in latest or code not in settings.get("divisions", {}):
            errors.append(f"Missing history or model configuration: {code}")
            continue
        last = pd.Timestamp(latest[code])
        age = (boundary - last).days
        leagues[code] = {"last_result_date": last.date().isoformat(), "age_days": age}
        if max_age_days is not None and age > max_age_days:
            errors.append(f"Stale results: {code} ({age} days > {max_age_days})")
    return {"ready": not errors, "errors": errors, "cutoff_exclusive": str(boundary.date()),
            "rows": len(data), "training_rows_before_cutoff": len(history),
            "competitions": leagues, "dataset_sha256": sha256(dataset),
            "config_sha256": sha256(config), "max_result_age_days": max_age_days,
            "limitation": "Recency does not certify complete coverage or pre-close availability."}


def require_ready(report):
    if not report["ready"]:
        raise ValueError("; ".join(report["errors"]))
