"""Chronological research on goal laws and context calibration, all three leagues."""
import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from quantfootball.models.calibration import calibrate_probabilities, fit_calibrator
from quantfootball.research.context_calibration import apply_context, fit_context
from quantfootball.research.diagnostics import PROBS, diagnose, metrics, paired_delta
from quantfootball.research.flexible_goals import FAMILIES, FlexibleGoalModel

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    with path.open('x',encoding='utf-8') as handle:
        json.dump(value,handle,indent=2,ensure_ascii=False,allow_nan=False,
                  default=lambda o:o.isoformat() if isinstance(o,(datetime,pd.Timestamp)) else str(o))


def original_reference(code,archive,settings):
    path = archive/f'dynamic_calibration_v1/{code}.incumbent.parquet'
    base = pd.read_parquet(path).sort_values(['date','match_id']).reset_index(drop=True)
    weight = settings['dynamic_weight']
    if weight:
        raw = pd.read_parquet(archive/f'dynamic_calibration_v1/{code}.raw.parquet')
        raw = raw[raw.candidate.eq(1)].set_index('match_id').reindex(base.match_id)
        if raw[PROBS].isna().any().any() or not np.array_equal(raw.result,base.result):
            raise ValueError('Missing original dynamic probabilities.')
        base[PROBS] = (1-weight)*base[PROBS].to_numpy()+weight*raw[PROBS].to_numpy()
    base['date'],base['cutoff'] = pd.to_datetime(base.date),pd.to_datetime(base.cutoff)
    return base


def calibrated(frame,cutoff,mode):
    if mode == 'context':
        fitted = fit_context(frame,cutoff,precision=100)
        predicted = apply_context(frame,fitted)
    else:
        fitted = fit_calibrator(frame,cutoff,mode=mode,precision=50)
        predicted = calibrate_probabilities(frame[PROBS].to_numpy(),fitted)
    output = frame.copy()
    output[PROBS] = predicted
    return output,fitted


def generate(history,base,settings,folder,code):
    indexed = history.set_index('match_id')
    targets = indexed.reindex(base.match_id).reset_index()
    if targets.result.isna().any() or not np.array_equal(targets.result,base.result):
        raise ValueError('Historical goals and archived targets differ.')
    targets['cutoff'] = base.cutoff.to_numpy()
    raw, fits = [], []
    begun = time.monotonic()
    for number,(cutoff,fixtures) in enumerate(targets.groupby('cutoff',sort=True)):
        for family in FAMILIES:
            model = FlexibleGoalModel(family=family,half_life_days=settings['half_life_days'],
                ridge=settings['ridge'],lookback_days=settings['lookback_days']).fit(history,cutoff)
            fits.append(model.diagnostics)
            for m in fixtures.itertuples(index=False):
                h,a = model.expected_goals(m.home_team,m.away_team,allow_unknown=True)
                p = model.predict_proba(m.home_team,m.away_team,allow_unknown=True)
                pleno = model.predict_pleno(m.home_team,m.away_team,allow_unknown=True)
                labels = ('0','1','2','M')
                actual = f'{labels[min(int(m.home_goals),3)]}-{labels[min(int(m.away_goals),3)]}'
                raw.append({'match_id':m.match_id,'date':m.date,'cutoff':cutoff,'season':m.season,
                    'competition_code':code,'result':m.result,'family':family,
                    'expected_home_goals':h,'expected_away_goals':a,'expected_total_goals':h+a,
                    'pleno_log_loss':float(-np.log(max(pleno[actual],1e-15))),
                    'pleno_brier':sum((v-(k == actual))**2 for k,v in pleno.items()),
                    **dict(zip(PROBS,[p['H'],p['D'],p['A']]))})
        if number%24 == 0:
            print(code,cutoff.date(),'weekly blocks',number+1,f'{time.monotonic()-begun:.1f}s',flush=True)
    frame = pd.DataFrame(raw)
    frame.to_parquet(folder/f'{code}.raw.parquet',index=False)
    save(folder/f'{code}.fits.json',fits)
    return frame,fits


def select(base,raw,settings,folder,code,archive):
    reference_context = raw[raw.family.eq('poisson')].set_index('match_id').reindex(base.match_id)
    base['expected_total_goals'] = reference_context.expected_total_goals.to_numpy()
    actual_current = pd.read_parquet(archive/f'dynamic_calibration_v1/{code}.selected.parquet')
    actual_current['date'] = pd.to_datetime(actual_current.date)
    expected = base[base.date >= '2024-07-01'].copy()
    expected[PROBS] = calibrate_probabilities(expected[PROBS].to_numpy(),settings['calibration'])
    matched = actual_current.set_index('match_id').reindex(expected.match_id)
    if not np.allclose(expected[PROBS].to_numpy(),matched[PROBS].to_numpy(),atol=1e-9,rtol=0):
        raise ValueError('The actual current model cannot be reproduced.')
    sources = {'reference':base.copy()}
    for family in FAMILIES:
        other = raw[raw.family.eq(family)].set_index('match_id').reindex(base.match_id)
        if other[PROBS].isna().any().any() or not np.array_equal(other.result,base.result):
            raise ValueError('Goal-family prediction targets are not identical.')
        for weight in (.25,.5,1.):
            out = base.copy()
            out[PROBS] = (1-weight)*base[PROBS].to_numpy()+weight*other[PROBS].to_numpy()
            sources[f'{family}_{weight:g}'] = out
    rank = []
    for name,frame in sources.items():
        for mode in ('identity','temperature','context'):
            pred,cal = calibrated(frame,'2023-07-01',mode)
            validation = pred[(pred.date >= '2023-07-01') & (pred.date < '2024-07-01')]
            rank.append({'name':name,'calibration':mode,'metrics':metrics(validation),
                         'calibration_fit':cal})
    rank.sort(key=lambda x:(x['metrics']['log_loss'],x['name'] != 'reference',x['calibration'] != 'identity',x['name']))
    # Freeze rank and winner before computing any new diagnostic scores.
    save(folder/f'{code}.selection.json',rank)
    winner = rank[0]
    diagnostics = {}
    for name,frame in sources.items():
        for mode in ('identity','temperature','context'):
            predicted,cal = calibrated(frame,'2024-07-01',mode)
            diagnostic = predicted[predicted.date >= '2024-07-01'].copy()
            label = name+'/'+mode
            diagnostics[label] = {'metrics':metrics(diagnostic),'vs_current':paired_delta(diagnostic,expected),
                'by_season':{s:metrics(g) for s,g in diagnostic.groupby('season')},'calibration_fit':cal}
            diagnostic.to_parquet(folder/f'{code}.{name}.{mode}.parquet',index=False)
    selected_label = winner['name']+'/'+winner['calibration']
    selected = pd.read_parquet(folder/f"{code}.{winner['name']}.{winner['calibration']}.parquet")
    result = {'selected_on_2023_24':winner,'selected_label':selected_label,
        'selected_diagnostic':diagnostics[selected_label],'current_metrics':metrics(expected),
        'selected_diagnostics_detail':diagnose(selected),'all_diagnostics':diagnostics,
        'standalone_goal_metrics':{family:{'one_x_two':metrics(g[g.date >= '2024-07-01']),
            'pleno_log_loss':float(g[g.date >= '2024-07-01'].pleno_log_loss.mean()),
            'pleno_brier':float(g[g.date >= '2024-07-01'].pleno_brier.mean())} for family,g in raw.groupby('family')},
        'current_reference_reproduced':True}
    save(folder/f'{code}.evaluation.json',result)
    print(code,'SELECTED',selected_label,'LL',result['selected_diagnostic']['metrics']['log_loss'],
          'current',result['current_metrics']['log_loss'],flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=False)
    archive = ROOT/'outputs/reports'
    configpath = ROOT/'configs/quiniela_dynamic_candidate.json'
    config = read(configpath)
    dataset_paths = {'men':ROOT/'data/processed/matches_spain.parquet','women':ROOT/'data/processed/matches_ligaf.parquet'}
    data = pd.concat([pd.read_parquet(p) for p in dataset_paths.values()],ignore_index=True)
    data['date'] = pd.to_datetime(data.date)
    data = data[data.date < '2026-07-01']
    source_paths = [Path(__file__),ROOT/'src/quantfootball/research/flexible_goals.py',
                    ROOT/'src/quantfootball/research/context_calibration.py',ROOT/'src/quantfootball/research/diagnostics.py',
                    ROOT/'src/quantfootball/models/calibration.py']
    protocol = {'created_at':datetime.now(UTC).isoformat(),'deployment_enabled':False,
        'status':'retrospective_research_on_previously_inspected_periods',
        'families':FAMILIES,'mixture_weights':[0,.25,.5,1],
        'calibration_modes':['identity','temperature','context'],
        'calibration_fit':['2022-07-01','2023-07-01'],'selection':['2023-07-01','2024-07-01'],
        'final_calibration_fit':['2022-07-01','2024-07-01'],'diagnostic':['2024-07-01','2026-07-01'],
        'primary_metric':'Mean log loss per competition on exact same fixtures; Brier and calibration secondary',
        'goal_prior':{'dispersion_precision':50,'shape_bounds':[.5,1000]},
        'context_prior':{'precision':100,'parameters':6},'config_sha256':digest(configpath),
        'dataset_sha256':{k:digest(p) for k,p in dataset_paths.items()},
        'sources_sha256':{str(p.relative_to(ROOT)):digest(p) for p in source_paths},
        'references':['https://arxiv.org/abs/2307.02139','https://doi.org/10.1111/1467-9884.00366'],
        'limitations':['These periods and baseline hyperparameters were already inspected; not fresh or fully nested confirmation',
            'Thirty model/calibration candidates per competition; bootstrap intervals do not correct model selection',
            'Goal models use per-competition global shape; shared-tempo dependence is nonnegative only',
            'No original Dixon-Coles low-score term in the new families; Poisson control isolates the distribution change',
            'Cold teams receive zero attack/defence prior; no new transfer, injuries, lineups or xG information',
            'Score-grid metrics concern standalone goal models; calibrated 1X2 mixtures do not inherit a joint goal grid',
            'No production promotion, future-market data, purchases or ROI claim']}
    save(args.output_dir/'protocol.json',protocol)
    for source in source_paths:
        target = args.output_dir/'source'/source.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(source.read_bytes())
    report = {'protocol':protocol,'divisions':{},'fits':{}}
    for code,settings in config['divisions'].items():
        base = original_reference(code,archive,settings)
        history = data[data.competition_code.eq(code)].copy()
        raw,fits = generate(history,base,settings,args.output_dir,code)
        if any(pd.Timestamp(f['training_last_date']) >= pd.Timestamp(f['cutoff']) for f in fits):
            raise ValueError('Future training result detected.')
        report['fits'][code] = {'total':len(fits),'converged':sum(f['converged'] for f in fits),
            'shape_at_bound':sum(f['dispersion_at_bound'] for f in fits),
            'shape_by_family':{fam:{'median':float(np.median([f['shape_k'] for f in fits if f['family'] == fam])),
                                   'minimum':min(f['shape_k'] for f in fits if f['family'] == fam),
                                   'maximum':max(f['shape_k'] for f in fits if f['family'] == fam)} for fam in FAMILIES if fam != 'poisson'}}
        report['divisions'][code] = select(base,raw,settings,args.output_dir,code,archive)
    save(args.output_dir/'evaluation.json',report)
    print('Flexible goal and context-calibration research complete.',flush=True)


if __name__ == '__main__':
    main()
