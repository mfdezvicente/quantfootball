"""Historical economic-data audit, independent of sporting eligibility and ROI.

Research reconstruction covers ordinary awards, empty lower categories and the
10-hit minimum. Equalization and sub-euro 11/12/13 prizes fail closed.
"""
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from itertools import pairwise

CATEGORIES = ('15', '14', '13', '12', '11', '10')
SHARES = {'15': Decimal('.075'), '14': Decimal('.16'), '13': Decimal('.075'),
          '12': Decimal('.075'), '11': Decimal('.075'), '10': Decimal('.09')}
CENT = Decimal('.01')


def money(value):
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('Money requires a decimal number.') from exc
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(CENT):
        raise ValueError('Money requires finite, nonnegative whole cents.')
    return amount


def parse_prizes(text):
    """Parse archived source lines even when the sporting table is incomplete."""
    pattern = r'^(?:L\d+@P\d+|QF):\s*(Pleno al 15|1[0-4] Aciertos)\s+([\d.]+)\s+([\d.,]+|BOTE)\s*$'
    found = {}
    for category, winners, unit in re.findall(pattern, text, re.MULTILINE):
        key = '15' if category.startswith('Pleno') else category[:2]
        count = int(winners.replace('.', ''))
        value = None if unit == 'BOTE' else str(money(unit.replace('.', '').replace(',', '.')))
        row = {'winners': count, 'unit_eur': value}
        if key in found and found[key] != row:
            raise ValueError(f'Conflicting prize data: {key}')
        if count > 0 and value is None:
            raise ValueError('Winners require a numeric published prize.')
        found[key] = row
    return found


def reconstruct(revenue, winners, *, rounding='fund_cent_then_unit', carry_in=None):
    """Use supplied final revenue/winner counts, never inferred or pre-close values.

    Two rounding conventions are diagnostic hypotheses; no official convention
    is asserted. Missing carry-in blocks special-category reconstruction.
    """
    revenue = money(revenue)
    if revenue == 0 or set(winners) != set(CATEGORIES):
        raise ValueError('Positive revenue and all six winner counts required.')
    if any(type(v) is not int or v < 0 for v in winners.values()):
        raise ValueError('Winner counts must be nonnegative integers.')
    if winners['15'] > winners['14']:
        raise ValueError('Pleno winners must be a subset of fourteen-hit winners.')
    if rounding not in ('fund_cent_then_unit', 'exact_fund_then_unit'):
        raise ValueError('Unknown rounding hypothesis.')
    funds = {k: revenue * share for k, share in SHARES.items()}
    if rounding == 'fund_cent_then_unit':
        funds = {k: v.quantize(CENT, rounding=ROUND_HALF_UP) for k, v in funds.items()}
    future = Decimal(0)
    events, units, status = [], {}, {}
    if winners['14'] == 0:
        future += funds['14']
        funds['14'] = Decimal(0)
        events.append('empty_14_to_future_special')
    for current, lower in [('13', '12'), ('12', '11'), ('11', '10')]:
        if winners[current] == 0:
            funds[lower] += funds[current]
            funds[current] = Decimal(0)
            events.append(f'empty_{current}_to_{lower}')
    # Equalization is checked before suppressing the ten-hit category; otherwise
    # a discarded small award could hide a preceding unequal-category branch.
    blockers = []
    paid = [k for k in ('14', '13', '12', '11', '10') if winners[k] and funds[k]]
    if any(funds[a] / winners[a] < funds[b] / winners[b] for a, b in pairwise(paid)):
        blockers.append('category_equalization_not_supported')
    if any(winners[k] and funds[k] / winners[k] < 1 for k in ('13', '12', '11')):
        blockers.append('sub_euro_upward_redistribution_not_supported')
    if winners['10'] == 0 or funds['10'] / winners['10'] < Decimal('1.50'):
        future += funds['10']
        funds['10'] = Decimal(0)
        events.append('empty_or_subminimum_10_to_future_special')
    for category in ('14', '13', '12', '11', '10'):
        if not winners[category]:
            units[category], status[category] = None, 'no_winners'
        elif blockers:
            units[category], status[category] = None, 'unsupported_rule_branch'
        else:
            units[category] = str((funds[category] / winners[category]).quantize(CENT, rounding=ROUND_HALF_UP))
            status[category] = 'reconstructed_under_rounding_hypothesis'
    if carry_in is not None:
        funds['15'] += money(carry_in)
    if winners['15'] == 0:
        units['15'], status['15'] = None, 'no_winners_carry_in_unknown' if carry_in is None else 'no_winners'
        future += funds['15']
    elif carry_in is None:
        units['15'], status['15'] = None, 'missing_special_carry_in'
    else:
        units['15'] = str((funds['15'] / winners['15']).quantize(CENT, rounding=ROUND_HALF_UP))
        status['15'] = 'reconstructed_under_rounding_hypothesis'
    return {'units_eur': units, 'status': status, 'events': events, 'blockers': blockers,
            'rounding_hypothesis': rounding, 'special_carry_in_eur': None if carry_in is None else str(money(carry_in)),
            'funds_eur': {k: str(v) for k, v in funds.items()},
            'generated_or_carried_future_eur': str(future),
            'future_pool_total_known': carry_in is not None,
            'economic_deployment_enabled': False}


def reconcile(record):
    """Compare to published units without fitting carry-in to those same awards."""
    prizes = record['prizes']
    results = []
    for rounding in ('fund_cent_then_unit', 'exact_fund_then_unit'):
        reconstructed = reconstruct(record['revenue_eur'], {k: v['winners'] for k, v in prizes.items()},
                                    rounding=rounding, carry_in=record.get('special_carry_in_eur'))
        comparisons = []
        for cat in CATEGORIES:
            published, expected = prizes[cat]['unit_eur'], reconstructed['units_eur'][cat]
            delta = None if published is None or expected is None else money(expected) - money(published)
            comparisons.append({'category': cat, 'winners': prizes[cat]['winners'],
                                'published_unit_eur': published, 'reconstructed_unit_eur': expected,
                                'delta_eur': None if delta is None else str(delta),
                                'matches': None if delta is None else delta == 0,
                                'status': reconstructed['status'][cat]})
        results.append(reconstructed | {'comparisons': comparisons})
    return results
