import copy

import numpy as np
import pandas as pd
import pytest

from quantfootball.research.ablation_features import GROUPS, additional_features, group_columns
from quantfootball.research.diagnostics import attach_roster_flags, diagnose, metrics, paired_delta


def history_case():
    return pd.DataFrame([
        {'match_id': str(i), 'date': pd.Timestamp(day), 'competition_code': code,
         'season': season, 'home_team': home, 'away_team': away,
         'home_goals': hg, 'away_goals': ag,
         'result': 'H' if hg > ag else 'D' if hg == ag else 'A'}
        for i,(day,code,season,home,away,hg,ag) in enumerate([
            ('2023-05-01','es.2','2022-23','A','B',1,0),
            ('2023-05-01','es.1','2022-23','C','D',2,1),
            ('2023-08-01','es.1','2023-24','A','C',0,2),
            ('2023-08-06','es.1','2023-24','D','A',1,1),
            ('2023-08-12','es.1','2023-24','A','D',3,1),
            ('2023-08-13','es.1','2023-24','C','A',1,0),
            ('2023-08-19','es.1','2023-24','A','C',2,0),
        ])])


def test_labels_and_future_results_do_not_enter_same_week_features():
    data = history_case()
    original = additional_features(data).set_index('match_id')
    modified = data.copy()
    modified.loc[modified.date >= '2023-08-07', ['home_goals','away_goals','result']] = [0,7,'A']
    revised = additional_features(modified).set_index('match_id')
    # Aug 12 and 13 share cutoff Aug 7. Their own or later labels cannot enter.
    pd.testing.assert_frame_equal(original.loc[['4','5']], revised.loc[['4','5']])
    assert not np.allclose(original.loc['6'], revised.loc['6'])


def test_future_append_does_not_change_existing_features():
    data = history_case()
    before = additional_features(data.iloc[:-1]).set_index('match_id')
    after = additional_features(data).set_index('match_id').loc[before.index]
    pd.testing.assert_frame_equal(before,after)


def test_groups_are_disjoint_and_features_are_finite():
    table = additional_features(history_case())
    groups = [set(group_columns(table,g)) for g in GROUPS]
    assert all(groups)
    assert sum(map(len,groups)) == len(set.union(*groups))
    assert np.isfinite(table.drop(columns='match_id').to_numpy()).all()
    with pytest.raises(ValueError):
        group_columns(table,'unknown')


def predictions():
    return pd.DataFrame({'match_id':['a','b'], 'date':['2023-08-12','2023-08-13'],
                         'result':['H','D'], 'p_home':[.8,.2], 'p_draw':[.1,.6], 'p_away':[.1,.2]})


def test_paired_comparison_aligns_ids_and_rejects_different_fixtures():
    left = predictions()
    right = left.iloc[::-1].copy()
    assert paired_delta(left,right)['mean_log_loss_difference'] == pytest.approx(0)
    assert paired_delta(left,right)['ci95'] is None  # Only one calendar week.
    with pytest.raises(ValueError, match='identical'):
        paired_delta(left,right.iloc[:1])
    right.loc[right.match_id.eq('a'),'result'] = 'D'
    with pytest.raises(ValueError, match='disagree'):
        paired_delta(left,right)


def test_calibration_and_draw_diagnostics_have_explicit_denominators():
    frame = predictions()
    result = diagnose(frame)
    assert result['segments']['draws']['matches'] == 1
    assert result['segments']['favorites_ge_70pct']['matches'] == 1
    assert result['segments']['promoted_from_es2']['matches'] == 0
    assert sum(b['matches'] for b in result['favorite_calibration']) == 2
    assert result['overall']['mean_draw_probability'] == pytest.approx(.35)
    assert result['overall']['observed_draw_rate'] == .5


def test_roster_flag_uses_previous_season_not_future_results():
    data = history_case()
    out = data.loc[data.match_id.eq('2'),['match_id','date','result']].copy()
    out['cutoff'] = pd.Timestamp('2023-07-31')
    out[['p_home','p_draw','p_away']] = [.5,.3,.2]
    annotated = attach_roster_flags(out,data)
    assert bool(annotated.promoted_from_es2.iloc[0])
    assert not bool(annotated.new_to_covered_leagues.iloc[0])
    changed = copy.deepcopy(data)
    changed.loc[changed.date >= '2023-08-01','home_team'] = 'FutureTeam'
    # Explicit fixture identity stays fixed; future roster labels cannot change prior membership.
    for name in ('home_team','away_team','competition_code','season'):
        out[name] = annotated[name].to_numpy()
    assert bool(attach_roster_flags(out,changed).promoted_from_es2.iloc[0])


@pytest.mark.parametrize('column,value',[('p_home',float('nan')),('p_draw',-.1),('p_away',0)])
def test_invalid_probability_diagnostics_are_rejected(column,value):
    frame = predictions()
    frame.loc[0,column] = value
    with pytest.raises(ValueError):
        metrics(frame)
