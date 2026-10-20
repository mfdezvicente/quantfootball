"""Exercise orchestration with simulated training; never contact providers."""
import copy
import importlib.util
import json
from datetime import timedelta
from pathlib import Path

import pytest
from test_economic_development import observation_case

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cycle():
    spec = importlib.util.spec_from_file_location('cycle', ROOT / 'scripts/run_prospective_cycle.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('failure', [None, 'missing_quotes', 'example', 'stale', 'training_failure'])
def test_cycle_uses_generated_probabilities_and_records_failures(cycle, tmp_path, monkeypatch, failure):
    now, forecast, obs = observation_case()
    for row, prediction in zip(obs['fixtures'], [*forecast['coupons'][0]['fixtures'], forecast['coupons'][0]['pleno']]):
        row['date'] = prediction['date']
        # Real observations contain no probability predictions.
        assert 'p_home' not in row
    quotes = []
    for row in obs['fixtures'][:14]:
        quotes.append({**row, 'quotes': [{'bookmaker': 'test', 'observed_at': now.isoformat(),
                                         'odds_1x2': [2, 3.5, 4]}]})
    snapshot = {'schema_version': 1, 'snapshot_at': now.isoformat(), 'retrieved_at': now.isoformat(),
                'source_url': 'https://example.org/odds', 'fixtures': quotes}
    if failure == 'missing_quotes':
        snapshot['fixtures'].pop()
    if failure == 'example':
        snapshot['is_example'] = True
    if failure == 'stale':
        for row in quotes:
            row['quotes'][0]['observed_at'] = (now - timedelta(days=3)).isoformat()
    for name, value in [('observation', obs), ('snapshot', snapshot)]:
        (tmp_path / f'{name}.json').write_text(json.dumps(value))
    out = tmp_path / 'run'
    monkeypatch.setattr('sys.argv', ['cycle', '--observation', str(tmp_path / 'observation.json'),
        '--snapshot', str(tmp_path / 'snapshot.json'), '--output-dir', str(out),
        '--decision-root', str(tmp_path / 'decisions'), '--pair-root', str(tmp_path / 'pairs')])
    # Keep actual observation, market and data validation. Only training and external
    # registration are mocked; no probability cohort is polluted by simulated data.
    events = []
    monkeypatch.setattr(cycle, 'register_decision', lambda *a: events.append('abstain'))
    def train(command, **kwargs):
        script = Path(command[1]).name
        if failure == 'training_failure':
            raise cycle.subprocess.CalledProcessError(1, command)
        folder = Path(command[command.index('--output-dir') + 1])
        folder.mkdir()
        payload = copy.deepcopy(forecast)
        if script == 'plan_market_pool.py':
            assert events == ['abstain', 'plan_spain.py']
            payload['coupons'][0]['market_comparison'] = {'tested': True}
        (folder / 'forecast.json').write_text(json.dumps(payload))
        events.append(script)
    monkeypatch.setattr(cycle.subprocess, 'run', train)
    monkeypatch.setattr(cycle, 'register_pair', lambda *a: events.append('pair'))
    monkeypatch.setattr(cycle, 'attach_market', lambda *a: events.append('attach'))
    if failure:
        with pytest.raises(SystemExit) as err:
            cycle.main()
        assert err.value.code == 2
    else:
        cycle.main()
    status = json.loads((out / 'run_status.json').read_text())
    assert status['registered_decision']
    assert status['registered_pair'] == (failure is None)
    if failure is None:
        assert status['market_preflight']['matched_fixtures'] == 14
        assert events == ['abstain', 'plan_spain.py', 'plan_market_pool.py', 'pair', 'attach']
    else:
        assert status['status'] == 'blocked_or_partial'
        assert 'plan_market_pool.py' not in events


def test_missing_input_keeps_a_diagnostic(cycle, tmp_path, monkeypatch):
    out = tmp_path / 'run'
    monkeypatch.setattr('sys.argv', ['cycle', '--observation', str(tmp_path / 'missing.json'),
        '--snapshot', str(tmp_path / 'also_missing.json'), '--output-dir', str(out)])
    with pytest.raises(SystemExit):
        cycle.main()
    status = json.loads((out / 'run_status.json').read_text())
    assert status['status'] == 'blocked_or_partial'
    assert not status['registered_pair']
