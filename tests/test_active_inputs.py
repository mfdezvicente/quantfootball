import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from quantfootball.data.active import inspect_inputs, require_ready, resolve_active, sha256

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def inputs(tmp_path):
    active = resolve_active(ROOT)
    data = pd.read_parquet(active['dataset'])
    # Keep valid historical rows with real identities and independent competitions.
    data = data.sort_values('date').groupby('competition_code').tail(1).copy()
    data['date'] = pd.Timestamp('2026-10-18')
    dataset = tmp_path / 'matches.parquet'
    data.to_parquet(dataset)
    return dataset, active['config']


def test_recency_checks_every_league(inputs):
    dataset, config = inputs
    data = pd.read_parquet(dataset)
    data.loc[data.competition_code.eq('es.w.1'), 'date'] = pd.Timestamp('2026-10-01')
    data.to_parquet(dataset)
    report = inspect_inputs(dataset, config, '2026-10-19')
    with pytest.raises(ValueError, match='es.w.1'):
        require_ready(report)


def test_future_rows_cannot_hide_missing_history(inputs):
    dataset, config = inputs
    data = pd.read_parquet(dataset)
    data.loc[data.competition_code.eq('es.w.1'), 'date'] = pd.Timestamp('2026-10-19')
    data.to_parquet(dataset)
    report = inspect_inputs(dataset, config, '2026-10-19')
    assert report['training_rows_before_cutoff'] == 2
    assert not report['ready']


def test_explicit_historical_mode_and_missing_config(inputs, tmp_path):
    dataset, config = inputs
    assert inspect_inputs(dataset, config, '2026-11-19', None)['ready']
    settings = json.loads(config.read_text())
    del settings['divisions']['es.w.1']
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(settings))
    assert not inspect_inputs(dataset, path, '2026-10-19')['ready']


def test_manifest_rejects_tampering_and_outside_root(tmp_path):
    spec = json.loads((ROOT / 'configs/active_inputs.json').read_text())
    for name in ('dataset', 'config', 'audit'):
        source = ROOT / spec[name]['path']
        target = tmp_path / source.name
        target.write_bytes(source.read_bytes())
        spec[name]['path'] = target.name
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps(spec))
    assert resolve_active(tmp_path, manifest)['dataset'].exists()
    (tmp_path / spec['config']['path']).write_text('{}')
    with pytest.raises(ValueError, match='hash changed'):
        resolve_active(tmp_path, manifest)
    spec['config'] = {'path': str(ROOT / 'configs/quiniela_dynamic_candidate.json'),
                      'sha256': sha256(ROOT / 'configs/quiniela_dynamic_candidate.json')}
    manifest.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match='outside'):
        resolve_active(tmp_path, manifest)


@pytest.mark.parametrize('base_date,snapshot_date,added,skipped', [
    ('20261014', '20261019', 27, {'FirstHalf', 'HalfTime'}),
    ('20261019', '20261028', 32, {'Abandoned', 'PreMatch'}),
])
def test_new_snapshot_preserves_old_rows_and_skips_live(base_date, snapshot_date, added, skipped):
    base = ROOT / f'data/processed/matches_quiniela_{base_date}.parquet'
    snapshot = ROOT / f'data/processed/matches_quiniela_{snapshot_date}.parquet'
    old = pd.read_parquet(base)
    new = pd.read_parquet(snapshot)
    keys = ['competition_code', 'season', 'home_team', 'away_team']
    restored = new.merge(old[keys], on=keys).sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(old.sort_values(keys).reset_index(drop=True), restored[old.columns])
    audit = json.loads(snapshot.with_suffix('.audit.json').read_text())
    assert audit['base_sha256'] == sha256(base)
    assert audit['dataset_sha256'] == sha256(snapshot)
    assert audit['added_rows'] == added == len(new) - len(old)
    assert {row['status'] for row in audit['skipped_source_rows']} == skipped


def test_cli_imports_without_execution():
    for name in ('plan_spain', 'probability_registry', 'run_prospective_cycle', 'check_active_inputs'):
        spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
        spec.loader.exec_module(importlib.util.module_from_spec(spec))
