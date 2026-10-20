import copy
import importlib.util
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from quantfootball.quiniela.prize_audit import (
    CATEGORIES,
    money,
    parse_prizes,
    reconcile,
    reconstruct,
)

ROOT = Path(__file__).resolve().parents[1]


def test_sources_have_independent_prize_tables():
    records = json.loads((ROOT / 'tests/fixtures/prize_observations_v1.json').read_text(encoding='utf-8'))
    for record in records:
        text = '\n'.join(p.read_text(encoding='utf-8') for p in (ROOT / 'data/raw/official_expanded').glob(record['contest_date'] + '*.txt'))
        assert parse_prizes(text) == record['prizes']


def test_official_examples_reconcile_paid_ordinary_awards():
    records = json.loads((ROOT / 'tests/fixtures/prize_observations_v1.json').read_text(encoding='utf-8'))
    compared = 0
    for record in records:
        result = reconcile(record)[0]
        assert not result['blockers']
        for row in result['comparisons']:
            if row['category'] != '15' and row['winners'] > 0:
                assert row['matches'], row
                compared += 1
    assert compared == 17


def test_special_requires_known_carry_in_and_adds_to_fourteen():
    record = json.loads((ROOT / 'tests/fixtures/prize_observations_v1.json').read_text(encoding='utf-8'))[-1]
    assert reconcile(record)[0]['status']['15'] == 'missing_special_carry_in'
    record['special_carry_in_eur'] = '0.00'  # Synthetic assumption, not an observed fact.
    calculated = reconcile(record)[0]['units_eur']
    assert calculated['15'] == '13491.99'
    assert Decimal(calculated['15']) + Decimal(calculated['14']) == Decimal('16277.43')


def test_zero_award_is_not_missing_or_no_winners():
    text = 'QF: 10 Aciertos 1000 0,00\nQF: Pleno al 15 0 BOTE'
    prizes = parse_prizes(text)
    assert prizes['10'] == {'winners': 1000, 'unit_eur': '0.00'}
    assert prizes['15'] == {'winners': 0, 'unit_eur': None}
    with pytest.raises(ValueError, match='Conflicting'):
        parse_prizes(text + '\nQF: 10 Aciertos 1000 1,00')


def test_missing_winner_category_and_minimum_boundary():
    winners = {'15': 0, '14': 1, '13': 10, '12': 100, '11': 500, '10': 600}
    assert reconstruct('10000.00', winners)['units_eur']['10'] == '1.50'
    winners['10'] = 601
    result = reconstruct('10000.00', winners)
    assert result['units_eur']['10'] == '0.00'
    assert 'empty_or_subminimum_10_to_future_special' in result['events']
    winners['13'] = 0
    result = reconstruct('10000.00', winners)
    assert result['units_eur']['12'] == '15.00'


def test_unimplemented_branches_fail_closed_even_before_minimum_filter():
    winners = {'15': 0, '14': 1, '13': 10, '12': 100, '11': 625, '10': 643}
    # Eleven would pay 1.20; ten would pay 1.399... before minimum suppression.
    result = reconstruct('10000.00', winners)
    assert 'category_equalization_not_supported' in result['blockers']
    assert result['units_eur']['11'] is None
    winners['11'] = 1000
    assert 'sub_euro_upward_redistribution_not_supported' in reconstruct('10000.00', winners)['blockers']


@pytest.mark.parametrize('bad', ['NaN', 'Infinity', '-1', '.001', 'unknown'])
def test_money_rejects_unusable_values(bad):
    with pytest.raises(ValueError):
        money(bad)


def test_archive_records_missing_sundays_and_conflicts(tmp_path):
    spec = importlib.util.spec_from_file_location('audit', ROOT / 'scripts/audit_prize_economics.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = '\n'.join(f'QF: {"Pleno al 15" if k == "15" else k + " Aciertos"} 0 0,00' for k in CATEGORIES)
    (tmp_path / '2024-08-04.txt').write_text(text)
    rows = module.audit_archive([tmp_path], date(2024, 8, 4), date(2024, 8, 11), [])
    assert len(rows) == 2
    assert rows[0]['prize_table_complete']
    assert not rows[1]['prize_table_complete']
    assert all(row['revenue_eur'] is None and not row['preclose_evidence'] for row in rows)
    record = {'contest_date': '2024-08-04', 'revenue_eur': '100.00',
              'prizes': copy.deepcopy(rows[0]['prizes'])}
    record['prizes']['14']['winners'] = 1
    rows = module.audit_archive([tmp_path], date(2024, 8, 4), date(2024, 8, 4), [record])
    assert rows[0]['status'] == 'conflict_or_invalid'
