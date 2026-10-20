"""Exact-fixture diagnostics and monthly, same-architecture feature ablations."""
import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from quantfootball.data.active import resolve_active
from quantfootball.data.results import ResultLookup
from quantfootball.data.sporting_status import SportingStatusLookup
from quantfootball.features.form import feature_columns
from quantfootball.market.match_study import verify_study
from quantfootball.market.snapshots import instant, key
from quantfootball.models.form import FormClassifier
from quantfootball.research.ablation_features import GROUPS, additional_features, group_columns
from quantfootball.research.diagnostics import (
    PROBS, attach_roster_flags, diagnose, metrics, paired_delta,
)

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False,
                  default=lambda obj: obj.isoformat() if isinstance(obj,(pd.Timestamp,datetime)) else str(obj))


def paired_market(root, history, status_folder):
    lookup = ResultLookup(history)
    statuses = SportingStatusLookup(status_folder)
    ready, excluded, seen, rows = [], [], set(), []
    for folder in sorted(root.iterdir()):
        if folder.is_dir():
            seal, report = verify_study(folder)
            ready.append((instant(seal['registered_at']), folder.name, report))
    for registered, name, report in sorted(ready):
        for f in report['comparison']['fixtures']:
            result = lookup.find(f, registered)
            exclusion = statuses.find(f, registered)
            identity = (*key(f), result['actual_date'] if result else f['date'][:10])
            if identity in seen:
                continue
            seen.add(identity)
            if result and exclusion:
                raise ValueError('Completed result conflicts with sporting exclusion.')
            if exclusion or result is None:
                excluded.append({'record': name, 'fixture': identity, 'status': 'sporting_excluded' if exclusion else 'pending'})
                continue
            rows.append({'match_id': result['match_id'], 'date': result['actual_date'],
                         'cutoff': report['cutoff'], 'result': result['result'],
                         'home_team': result['home_team'], 'away_team': result['away_team'],
                         'competition_code': result['competition_code'], 'record': name,
                         'registered_at': registered.isoformat(),
                         'model_p': f['model_1x2'], 'market_p': f['market_1x2']})
    leagues = {}
    frame = pd.DataFrame(rows)
    for code in ('es.1','es.2','es.w.1'):
        selected = frame[frame.competition_code.eq(code)].copy()
        if selected.empty:
            leagues[code] = {'paired_matches': 0, 'status': 'no_archived_market_quotes'}
            continue
        selected = attach_roster_flags(selected, history)
        outputs = {}
        for name in ('model','market','pool50_retrospective'):
            part = selected.drop(columns=['model_p','market_p']).copy()
            probabilities = (np.array(selected.model_p.tolist()) if name == 'model'
                else np.array(selected.market_p.tolist()) if name == 'market'
                else .5 * (np.array(selected.model_p.tolist()) + np.array(selected.market_p.tolist())))
            part[PROBS] = probabilities
            outputs[name] = part
        leagues[code] = {'paired_matches': len(selected),
                         **{name: diagnose(part) for name,part in outputs.items()},
                         'model_vs_market': paired_delta(outputs['model'],outputs['market']),
                         'pool50_vs_market': paired_delta(outputs['pool50_retrospective'], outputs['market']),
                         'note': 'Pool50 is a retrospective diagnostic on these fixtures, not the separate prospective cohort.'}
    return {'leagues': leagues, 'exclusions': excluded, 'fixture_rows': rows,
            'scope': 'All verified market studies; first registration per sporting fixture; no winner-based selection.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--groups', nargs='+', choices=GROUPS, default=list(GROUPS))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    active = resolve_active(ROOT)
    current = pd.read_parquet(active['dataset'])
    archive = ROOT / 'outputs/reports'
    settings = json.loads(active['config'].read_text(encoding='utf-8'))
    historical_path = ROOT / 'data/processed/matches_spain.parquet'
    historical = pd.read_parquet(historical_path)
    historical = historical[historical.date < '2026-07-01'].copy()
    protocol = {'created_at': datetime.now(UTC).isoformat(),
        'status': 'retrospective_research_only', 'deployment_enabled': False,
        'selection_period': ['2022-07-01','2024-07-01'], 'diagnostic_period': ['2024-07-01','2026-07-01'],
        'groups': args.groups, 'architecture': {code: settings['divisions'][code]['form_parameters'] for code in ('es.1','es.2')},
        'method': 'Replace only the fixed 25% form head; pooled male training; original feature versions and monthly coefficient cutoff; one feature group at a time.',
        'dataset_sha256': digest(historical_path), 'active_dataset_sha256': digest(active['dataset']),
        'active_config_sha256': digest(active['config']),
        'source_sha256': {str(p.relative_to(ROOT)): digest(p) for p in [Path(__file__),
            ROOT/'src/quantfootball/research/ablation_features.py', ROOT/'src/quantfootball/research/diagnostics.py',
            ROOT/'src/quantfootball/models/form.py', ROOT/'src/quantfootball/features/form.py']},
        'limitations': ['Historical selection/diagnostic periods were inspected before; no untouched confirmation',
            'New groups and fixed online-goal constants are declared now, after previous historical research',
            'Monthly rolling fits use only prior labels; statistical intervals do not correct repeated model selection',
            'League-only rest/congestion, final archived schedule dates; no cups, Europe, xG, injuries or publication-time proof',
            'Dynamic features are a fixed online goal-state proxy, not the existing full dynamic MAP goal model',
            'Controlled feature experiments are male only; Liga F diagnosed with its own frozen goal model',
            'No production model or the fixed prospective 50/50 protocol is promoted by this run']}
    # Declare architecture, groups and scoring windows before computing new scores.
    save(args.output_dir / 'protocol.json', protocol)
    historical_diagnostics = {}
    for code in ('es.1','es.2','es.w.1'):
        selected = pd.read_parquet(archive / f'dynamic_calibration_v1/{code}.selected.parquet')
        selected = attach_roster_flags(selected, current)
        historical_diagnostics[code] = diagnose(selected)
        selected.to_parquet(args.output_dir / f'{code}.diagnostic_fixtures.parquet', index=False)
    market = paired_market(ROOT/'outputs/predictions/market_matches', current, ROOT/'data/raw/results_20261014')
    save(args.output_dir / 'diagnostics.json', {'historical': historical_diagnostics, 'paired_market': market})
    print('Diagnostics ready; starting controlled monthly feature experiments.', flush=True)
    extra = additional_features(historical)
    extra.to_parquet(args.output_dir / 'additional_features.parquet', index=False)
    experiment = {'protocol': protocol, 'diagnostics': historical_diagnostics, 'paired_market': market, 'divisions': {}}
    for code in ('es.1','es.2'):
        config = settings['divisions'][code]
        if (config['form_weight'] != .25 or config['form_temperature'] != 1
                or config['dynamic_weight'] != 0 or config['calibration']['mode'] != 'identity'):
            raise ValueError('Archived-head replacement only supports this declared incumbent architecture.')
        source = 'form_v2_complete' if config['form_feature_version'] == 2 else 'form_v1'
        candidate = 3 if code == 'es.1' else 2
        basepath = archive/source/'features.parquet'
        feature_table = pd.read_parquet(basepath)
        feature_table = feature_table[feature_table.date < '2026-07-01'].copy()
        headpath = archive/source/f'candidate_{candidate}.parquet'
        head = pd.read_parquet(headpath)
        head = head[head.competition_code.eq(code)].copy().sort_values(['date','match_id']).reset_index(drop=True)
        full = feature_table.merge(extra, on='match_id', validate='one_to_one')
        if len(full) != len(feature_table):
            raise ValueError('Extra features do not cover every archived training fixture.')
        incumbent_path = archive/f'dynamic_calibration_v1/{code}.incumbent.parquet'
        incumbent = pd.read_parquet(incumbent_path).set_index('match_id').reindex(head.match_id).reset_index()
        if incumbent[PROBS].isna().any().any() or not np.array_equal(incumbent.result,head.result):
            raise ValueError('Incumbent fixture identities/results differ from the head archive.')
        targets = feature_table[(feature_table.date >= '2022-07-01') & (feature_table.date < '2026-07-01')].copy()
        targets['month'] = targets.cutoff.dt.to_period('M')
        cuts = targets.groupby('month').cutoff.min()
        check_cuts = sorted(set([cuts.iloc[0],cuts[cuts >= '2024-07-01'].iloc[0],cuts.iloc[-1]]))
        checks = []
        # Verify that current original class reproduces archived coefficients exactly.
        for cut in check_cuts:
            group = full[(full.competition_code == code) & (full.cutoff.dt.to_period('M') == cut.to_period('M'))]
            model = FormClassifier(config['form_parameters']).fit(feature_table, cut)
            cached = head.set_index('match_id').reindex(group.match_id)
            error = float(np.max(np.abs(model.predict_proba(group) - cached[PROBS].to_numpy())))
            if not np.isfinite(error) or error > 1e-7:
                raise ValueError(f'Baseline reproduction failed for {code}: {error}')
            checks.append({'coefficient_cutoff': cut.isoformat(), 'max_probability_difference': error})
        division = {'baseline_reproduction': checks, 'input_sha256': {str(p):digest(p) for p in [basepath,headpath,incumbent_path]},
                    'variants': {}, 'feature_version': config['form_feature_version']}
        for name in ['base',*args.groups]:
            if name == 'base':
                output = incumbent.copy()
                feature_count = len(feature_columns(feature_table))
                fitting = []
            else:
                features = list(feature_table.columns) + group_columns(extra,name)
                table = full[features]
                predictions, fitting = [], []
                started = time.monotonic()
                for number,(month,cut) in enumerate(cuts.items()):
                    group = table[(table.competition_code == code) & (table.cutoff.dt.to_period('M') == month)]
                    if group.empty:
                        continue
                    model = FormClassifier(config['form_parameters']).fit(table,cut)
                    batch = group[['match_id','date','cutoff','season','competition_code','result']].copy()
                    batch[PROBS] = model.predict_proba(group)
                    predictions.append(batch)
                    fitting.append({'month': str(month), 'coefficient_cutoff':cut.isoformat(),
                                    'training_last_date':model.training_last_date, 'iterations':model.iterations})
                    if number % 12 == 0:
                        print(code,name,month,f'{time.monotonic()-started:.1f}s',flush=True)
                revised_head = pd.concat(predictions).set_index('match_id').reindex(head.match_id)
                if revised_head[PROBS].isna().any().any():
                    raise ValueError('Revised head is missing paired fixture predictions.')
                output = incumbent.copy()
                output[PROBS] = incumbent[PROBS].to_numpy() + .25 * (revised_head[PROBS].to_numpy() - head[PROBS].to_numpy())
                if (output[PROBS].to_numpy() <= 0).any() or not np.allclose(output[PROBS].sum(axis=1),1):
                    raise ValueError('Replacement probabilities are invalid.')
                feature_count = len(feature_columns(table))
            output['date'], output['cutoff'] = pd.to_datetime(output.date), pd.to_datetime(output.cutoff)
            output.to_parquet(args.output_dir/f'{code}.{name}.parquet',index=False)
            val = output[output.date < '2024-07-01'].copy()
            diagnostic = output[output.date >= '2024-07-01'].copy()
            reference = incumbent[pd.to_datetime(incumbent.date) >= '2024-07-01'].copy()
            division['variants'][name] = {'selection_metrics': metrics(val), 'diagnostic_metrics': metrics(diagnostic),
                'vs_base': paired_delta(diagnostic,reference), 'feature_count': feature_count,
                'by_season': {s: metrics(g) for s,g in diagnostic.groupby('season')}, 'fits':fitting}
            print(code,name,'diagnostic LL',division['variants'][name]['diagnostic_metrics']['log_loss'],flush=True)
        # Ranking uses only earlier selection scores, independent of diagnostic rank.
        ranking = sorted(division['variants'],key=lambda n:(division['variants'][n]['selection_metrics']['log_loss'],n!='base',n))
        division['selection_ranking'] = ranking
        division['selection_winner'] = ranking[0]
        division['diagnostic_winner_descriptive_only'] = min(division['variants'], key=lambda n:division['variants'][n]['diagnostic_metrics']['log_loss'])
        experiment['divisions'][code] = division
        save(args.output_dir/f'{code}.evaluation.json',division)
    save(args.output_dir/'evaluation.json',experiment)
    print('Research completed without production promotion.',flush=True)


if __name__ == '__main__':
    main()
