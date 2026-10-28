"""The legacy updater delegates safely to the explicit immutable snapshot CLI."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

from quantfootball.data.openfootball import normalize_payload

ROOT = Path(__file__).resolve().parents[1]


def run_alias(*args):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src"), env.get("PYTHONPATH", "")]
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/update_current_dataset.py"), *map(str, args)],
        capture_output=True, text=True, env=env, check=False,
    )


def test_legacy_command_without_arguments_requires_explicit_inputs():
    result = run_alias()
    assert result.returncode == 2
    assert "Deprecated entry point" in result.stderr
    assert all(flag in result.stderr for flag in ("--base", "--snapshot", "--as-of", "--output"))


def test_legacy_command_never_overwrites_existing_output(tmp_path):
    target = tmp_path / "existing.parquet"
    target.write_bytes(b"preserve historical bytes")
    result = run_alias(
        "--base", tmp_path / "missing.parquet", "--snapshot", tmp_path / "missing",
        "--as-of", "2020-09-03", "--output", target,
    )
    assert result.returncode == 2
    assert "historical snapshots are immutable" in result.stderr
    assert target.read_bytes() == b"preserve historical bytes"
    assert not target.with_suffix(".audit.json").exists()


def test_legacy_command_delegates_complete_explicit_snapshot_update(tmp_path):
    base = tmp_path / "base.parquet"
    frame = normalize_payload({"matches": [{
        "date": "2020-09-01", "time": "18:00", "round": "1",
        "team1": "Real Madrid", "team2": "Sevilla", "score": [1, 0],
    }]}, "2020-21", "es.1")
    frame["gender"] = "men"
    frame.to_parquet(base, index=False)
    original = base.read_bytes()
    snapshots = tmp_path / "capture"
    snapshots.mkdir()
    capture = {
        "source_url": "https://www.laliga.com/laliga-easports/resultados/2020-21/jornada-2",
        "season": "2020-21", "matchday": 2, "fetched_at": "2020-09-03T10:00:00+00:00",
        "matches": [{
            "id": 99, "date": "2020-09-02T16:00:00+00:00", "status": "FullTime",
            "home_team": "Barcelona", "away_team": "Valencia",
            "home_score": 2, "away_score": 1,
        }],
    }
    (snapshots / "2020-es.1-02.json").write_text(json.dumps(capture), encoding="utf-8")
    target = tmp_path / "updated.parquet"
    result = run_alias(
        "--base", base, "--snapshot", snapshots, "--as-of", "2020-09-03", "--output", target,
    )
    assert result.returncode == 0, result.stderr
    assert "Deprecated entry point" in result.stderr
    summary = json.loads(result.stdout)
    assert summary["rows"] == 2 and summary["added_rows"] == 1
    assert len(pd.read_parquet(target)) == 2
    assert base.read_bytes() == original
    assert target.with_suffix(".audit.json").exists()
