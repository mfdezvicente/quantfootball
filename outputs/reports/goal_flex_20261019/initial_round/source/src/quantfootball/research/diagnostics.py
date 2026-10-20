"""Probability diagnostics on exact paired fixtures, with explicit sample counts."""
import numpy as np
import pandas as pd

PROBS = ['p_home', 'p_draw', 'p_away']
LABELS = ('H', 'D', 'A')


def validate(frame):
    if frame.empty or frame.match_id.duplicated().any() or not frame.result.isin(LABELS).all():
        raise ValueError('Unique labelled fixtures required.')
    p = frame[PROBS].to_numpy(dtype=float)
    if not np.isfinite(p).all() or (p <= 0).any() or not np.allclose(p.sum(axis=1), 1, atol=1e-8):
        raise ValueError('Invalid probabilities.')


def metrics(frame):
    validate(frame)
    p = frame[PROBS].to_numpy()
    y = np.array([LABELS.index(s) for s in frame.result])
    target = np.eye(3)[y]
    favorite = p.argmax(axis=1)
    return {'matches': len(frame), 'log_loss': float(-np.log(p[np.arange(len(p)), y]).mean()),
            'brier': float(((p-target)**2).sum(axis=1).mean()),
            'accuracy': float((favorite == y).mean()),
            'mean_draw_probability': float(p[:, 1].mean()), 'observed_draw_rate': float((y == 1).mean()),
            'draw_binary_brier': float(((p[:, 1]-(y == 1))**2).mean())}


def paired_delta(left, right, draws=2000):
    validate(left)
    validate(right)
    if set(left.match_id) != set(right.match_id):
        raise ValueError('Paired comparison requires identical fixture sets.')
    l = left.set_index('match_id').sort_index()
    r = right.set_index('match_id').reindex(l.index)
    if not l.result.equals(r.result) or not pd.to_datetime(l.date).equals(pd.to_datetime(r.date)):
        raise ValueError('Paired dates or outcomes disagree.')
    y = np.array([LABELS.index(s) for s in l.result])
    delta = -np.log(l[PROBS].to_numpy()[np.arange(len(l)), y]) + np.log(r[PROBS].to_numpy()[np.arange(len(l)), y])
    weeks = pd.to_datetime(l.date).dt.to_period('W-SUN').astype(str)
    blocks = pd.DataFrame({'week': weeks.to_numpy(), 'delta': delta}).groupby('week').delta.agg(['sum','size'])
    result = {'mean_log_loss_difference': float(delta.mean()), 'weeks': len(blocks), 'ci95': None,
              'interpretation': 'Exploratory paired resampling of calendar weeks; no selection correction or deployment proof.'}
    if len(blocks) >= 8:
        rng = np.random.default_rng(20261019)
        indices = rng.integers(0, len(blocks), size=(draws, len(blocks)))
        estimates = blocks['sum'].to_numpy()[indices].sum(axis=1) / blocks['size'].to_numpy()[indices].sum(axis=1)
        result['ci95'] = np.quantile(estimates, [.025,.975]).tolist()
    return result


def diagnose(frame):
    validate(frame)
    p = frame[PROBS].to_numpy()
    y = np.array([LABELS.index(s) for s in frame.result])
    favorite, confidence = p.argmax(axis=1), p.max(axis=1)
    bins, class_bins = [], {}
    for lower, upper in [(0,.5),(.5,.6),(.6,.7),(.7,.8),(.8,1.0000001)]:
        mask = (confidence >= lower) & (confidence < upper)
        bins.append({'lower': lower, 'upper': min(1,upper), 'matches': int(mask.sum()),
                     'mean_probability': float(confidence[mask].mean()) if mask.any() else None,
                     'observed_accuracy': float((favorite[mask] == y[mask]).mean()) if mask.any() else None})
    for j, label in enumerate(LABELS):
        rows = []
        for lower, upper in [(0,.1),(.1,.2),(.2,.3),(.3,.4),(.4,.5),(.5,.7),(.7,1.0000001)]:
            mask = (p[:,j] >= lower) & (p[:,j] < upper)
            rows.append({'lower': lower, 'upper': min(1,upper), 'matches': int(mask.sum()),
                         'mean_probability': float(p[mask,j].mean()) if mask.any() else None,
                         'observed_frequency': float((y[mask] == j).mean()) if mask.any() else None})
        class_bins[label] = rows
    segments = {}
    for name, mask in [('draws', y == 1), ('favorites_ge_70pct', confidence >= .7),
                       ('promoted_from_es2', frame.get('promoted_from_es2', pd.Series(False,index=frame.index)).to_numpy()),
                       ('new_to_covered_leagues', frame.get('new_to_covered_leagues',pd.Series(False,index=frame.index)).to_numpy())]:
        mask = np.asarray(mask,dtype=bool)
        segments[name] = metrics(frame.loc[mask]) if mask.any() else {'matches': 0}
    losses = -np.log(p[np.arange(len(p)), y])
    worst = frame.copy()
    worst['loss'] = losses
    columns = [c for c in ['match_id','date','home_team','away_team','result',*PROBS,'loss'] if c in worst]
    return {'overall': metrics(frame), 'favorite_calibration': bins, 'class_calibration': class_bins,
            'segments': segments, 'worst_15': worst.sort_values('loss',ascending=False)[columns].to_dict('records'),
            'warning': 'Outcome-conditioned draw diagnostics are descriptive; do not tune a blanket draw correction on these slices.'}


def attach_roster_flags(predictions, history):
    """Use only observed earlier-season membership; lower leagues may be missing."""
    hist = history.copy()
    hist['date'] = pd.to_datetime(hist.date)
    indexed = hist.set_index('match_id')
    out = predictions.copy()
    out['date'] = pd.to_datetime(out.date)
    for name in ('home_team','away_team','competition_code','season'):
        if name not in out:
            out[name] = indexed.reindex(out.match_id)[name].to_numpy()
    promoted, newcomers = [], []
    for m in out.itertuples(index=False):
        year = int(m.season[:4]) - 1
        previous = f'{year}-{str(year+1)[-2:]}'
        before = hist[(hist.season == previous) & (hist.date < pd.Timestamp(m.cutoff))]
        relevant = before[before.competition_code.isin(['es.1','es.2'])] if m.competition_code != 'es.w.1' else before[before.competition_code.eq('es.w.1')]
        teams = {code: set(g.home_team) | set(g.away_team) for code,g in relevant.groupby('competition_code')}
        known = set().union(*teams.values()) if teams else set()
        promoted.append(m.competition_code == 'es.1' and any(t in teams.get('es.2',set()) and t not in teams.get('es.1',set()) for t in (m.home_team,m.away_team)))
        newcomers.append(bool(known) and any(t not in known for t in (m.home_team,m.away_team)))
    out['promoted_from_es2'], out['new_to_covered_leagues'] = promoted, newcomers
    return out
