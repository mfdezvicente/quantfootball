"""Additional strictly prior-result features for controlled form-head ablations."""
from collections import defaultdict, deque

import numpy as np
import pandas as pd

from quantfootball.models.transfer_elo import TransferElo

GROUPS = ('opponents', 'dynamic', 'rest', 'congestion', 'transfer')


def additional_features(history):
    data = history.copy()
    data['date'] = pd.to_datetime(data.date)
    if (data.empty or data.date.isna().any() or data.match_id.duplicated().any()
            or not data.competition_code.isin(['es.1', 'es.2']).all()):
        raise ValueError('Unique dated male league fixtures required.')
    data = data.sort_values(['date', 'home_team'], kind='stable')
    data['cutoff'] = data.date - pd.to_timedelta(data.date.dt.dayofweek, unit='D')
    records = list(data.itertuples(index=False))
    games = defaultdict(lambda: deque(maxlen=100))
    state = defaultdict(lambda: np.zeros(2))  # attack, defensive weakness
    league = defaultdict(lambda: np.array([1.4, 1.1]))
    elo = TransferElo(league_gap=200, carryover=.75, newcomer_penalty=80)
    cursor, rows = 0, []
    for cutoff, block in data.groupby('cutoff', sort=True):
        while cursor < len(records) and records[cursor].date < cutoff:
            m = records[cursor]
            probs = elo.predict_proba(m.home_team, m.away_team, m.competition_code, m.season)
            # All historical updates are complete before this decision cutoff.
            h, a = state[m.home_team].copy(), state[m.away_team].copy()
            rates = league[m.competition_code] * np.exp([h[0] + a[1], a[0] + h[1]])
            residual = np.clip((np.array([m.home_goals, m.away_goals]) - rates) / np.sqrt(1 + rates), -3, 3)
            for team, side, other in [(m.home_team, 0, 1), (m.away_team, 1, 0)]:
                won = m.home_goals > m.away_goals if side == 0 else m.away_goals > m.home_goals
                points = 3 * won + (m.home_goals == m.away_goals)
                expected_points = 3 * probs['H' if side == 0 else 'A'] + probs['D']
                games[team].append((m.date, m.competition_code, float(points - expected_points)))
                state[team] = np.clip(.995 * state[team] + .03 * np.array([residual[side], residual[other]]), -1.5, 1.5)
            league[m.competition_code] = .99 * league[m.competition_code] + .01 * np.array([m.home_goals, m.away_goals])
            elo.update(m.home_team, m.away_team, m.competition_code, m.season, m.result)
            cursor += 1
        for m in block.itertuples(index=False):
            pair = []
            for team in (m.home_team, m.away_team):
                past = list(games[team])
                last = past[-1][0] if past else None
                recent = past[-20:]
                consecutive = 0
                for game in reversed(past):
                    if game[1] != m.competition_code:
                        break
                    consecutive += 1
                pair.append({
                    'opponents_points_residual5': sum(g[2] for g in past[-5:]) / (len(past[-5:]) + 5),
                    'opponents_points_residual20': sum(g[2] for g in recent) / (len(recent) + 5),
                    'dynamic_attack': float(state[team][0]),
                    'dynamic_defensive_weakness': float(state[team][1]),
                    'rest_since_known_game_log': float(np.log1p(min(60, (m.date - last).days) if last is not None else 60)),
                    'rest_unknown': float(last is None),
                    **{f'congestion_league_games{days}': sum(0 < (cutoff - g[0]).days <= days for g in past) for days in (7, 14, 28)},
                    'transfer_previous_division_fraction': sum(g[1] != m.competition_code for g in recent) / max(1, len(recent)),
                    'transfer_consecutive_current_division': min(20, consecutive),
                })
            row = {'match_id': m.match_id}
            for name in pair[0]:
                row.update({'home_research_' + name: pair[0][name], 'away_research_' + name: pair[1][name],
                            'diff_research_' + name: pair[0][name] - pair[1][name]})
            rows.append(row)
    return pd.DataFrame(rows)


def group_columns(table, group):
    if group not in GROUPS:
        raise ValueError('Unknown feature group.')
    return [c for c in table if '_research_' + group + '_' in c]
