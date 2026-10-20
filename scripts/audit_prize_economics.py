"""Inventory every declared Sunday, reconcile supplied economic facts, replay cash."""
import argparse
import hashlib
import html
import json
import re
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from quantfootball.quiniela.prize_audit import CATEGORIES, money, parse_prizes, reconcile
from quantfootball.quiniela.settlement import settle_columns

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)


def audit_archive(raw_dirs, start, end, observations):
    if start > end or start.weekday() != 6 or end.weekday() != 6:
        raise ValueError('Declare an ordered window with Sunday endpoints.')
    examples = {o['contest_date']: o for o in observations}
    if len(examples) != len(observations):
        raise ValueError('Duplicate economic observations.')
    rows = []
    day = start
    while day <= end:
        stamp = day.isoformat()
        paths = sorted({p.resolve() for root in raw_dirs for p in root.glob(stamp + '*.txt')})
        text = '\n'.join(p.read_text(encoding='utf-8') for p in paths)
        urls = sorted(set(re.findall(r'https://[^\s]+', text)))
        row = {'contest_date': stamp, 'files_sha256': {str(p): digest(p) for p in paths},
               'source_urls': urls, 'publication_timestamp': None,
               'legacy_capture_timestamp': None, 'preclose_evidence': False,
               'revenue_eur': None, 'special_carry_in_eur': None}
        try:
            prizes = parse_prizes(text)
            row['prizes'] = prizes
            row['prize_table_complete'] = set(prizes) == set(CATEGORIES)
            row['status'] = 'complete_prize_table' if row['prize_table_complete'] else 'incomplete_prize_table'
            row['published_gross_paid_eur'] = (str(sum((Decimal(p['unit_eur']) * p['winners']
                for p in prizes.values() if p['unit_eur'] is not None), Decimal(0)))
                if row['prize_table_complete'] else None)
            row['zero_award_categories'] = [k for k, p in prizes.items() if p['winners'] > 0 and p['unit_eur'] == '0.00']
            row['empty_categories'] = [k for k, p in prizes.items() if p['winners'] == 0]
            if stamp in examples:
                obs = examples[stamp]
                if prizes and prizes != obs['prizes']:
                    raise ValueError('Fresh source numeric observation conflicts with legacy archive.')
                if not row['prize_table_complete']:
                    row['prizes'] = obs['prizes']
                    row['prize_table_complete'] = True
                    row['status'] = 'complete_prize_table'
                row['revenue_eur'] = str(money(obs['revenue_eur']))
                row['economic_observation'] = obs
                row['reconstruction'] = reconcile(obs)
                row['published_gross_paid_eur'] = str(sum((Decimal(p['unit_eur']) * p['winners']
                    for p in row['prizes'].values() if p['unit_eur'] is not None), Decimal(0)))
                row['zero_award_categories'] = [k for k, p in row['prizes'].items()
                    if p['winners'] > 0 and p['unit_eur'] == '0.00']
                row['empty_categories'] = [k for k, p in row['prizes'].items() if p['winners'] == 0]
        except (ValueError, KeyError, TypeError) as exc:
            row['status'] = 'conflict_or_invalid'
            row['reason'] = str(exc)
        rows.append(row)
        day += timedelta(days=7)
    return rows


def replay(backtest, rows):
    source = json.loads(backtest.read_text(encoding='utf-8'))
    archive = {r['contest_date']: r for r in rows}
    result, totals = [], {}
    for coupon in source['coupons']:
        stamp = coupon['date']
        official = coupon['official']
        record = archive.get(stamp)
        for name, strategy in coupon['budgets']['5.00']['strategies'].items():
            row = {'contest_date': stamp, 'strategy': name}
            try:
                if not record or not record.get('prize_table_complete') or record['status'] == 'conflict_or_invalid':
                    raise ValueError('Missing/conflicting independent archive prize table.')
                if record['prizes'] != official['prizes']:
                    raise ValueError('Frozen experiment prize table differs from archived source.')
                actual = [f['sign'] for f in official['fixtures']]
                recalculated = settle_columns(strategy['columns'], actual, record['prizes'],
                    pleno_prediction=coupon['pleno']['prediction'], pleno_actual=coupon['pleno']['actual'])
                previous = coupon['settlement'][name]
                fields = ('cost_eur', 'gross_return_eur', 'net_eur', 'column_hits', 'max_hits')
                if any(recalculated[k] != previous[k] for k in fields):
                    raise ValueError('Cash replay differs from historical report.')
                row.update(status='reproduced', **recalculated)
                total = totals.setdefault(name, {'contests': 0, 'cost': Decimal(0), 'gross': Decimal(0)})
                total['contests'] += 1
                total['cost'] += Decimal(str(recalculated['cost_eur']))
                total['gross'] += Decimal(str(recalculated['gross_return_eur']))
            except (ValueError, KeyError, TypeError) as exc:
                row.update(status='not_reproduced', reason=str(exc))
            result.append(row)
    return {'source_path': str(backtest), 'source_sha256': digest(backtest), 'rows': result,
            'counts': dict(Counter(r['status'] for r in result)),
            'strategy_totals': {k: {'contests': v['contests'], 'cost_eur': str(v['cost']),
                'gross_eur': str(v['gross']), 'net_eur': str(v['gross'] - v['cost']),
                'roi': float((v['gross'] - v['cost']) / v['cost'])} for k, v in totals.items()},
            'limitations': 'Replays published gross units with frozen awarded signs; not an independent verification of signs, a purchase, net tax return or pre-close prize prediction.'}


def render(report):
    s = report['summary']
    cells = ''.join(f'<article><strong>{value}</strong><span>{label}</span></article>' for value, label in [
        (s['declared_sundays'], 'Domingos auditados'), (s['complete_prize_tables'], 'Tablas completas'),
        (s['revenue_observations'], 'Recaudaciones contrastadas'),
        (s['preclose_economic_records'], 'Registros económicos anteriores al cierre')])
    table = ''
    for r in report['rows']:
        table += '<tr>' + ''.join(f'<td>{html.escape(str(x))}</td>' for x in [r['contest_date'],
            r['status'], r['revenue_eur'] or 'Desconocida',
            ', '.join(r.get('zero_award_categories', [])) or '—',
            ', '.join(r.get('empty_categories', [])) or '—',
            r.get('published_gross_paid_eur') or 'Desconocido']) + '</tr>'
    comparisons = ''
    for r in report['rows']:
        for hypothesis in r.get('reconstruction', []):
            if hypothesis['rounding_hypothesis'] != 'fund_cent_then_unit':
                continue
            for c in hypothesis['comparisons']:
                if c['winners'] == 0:
                    continue
                comparisons += '<tr>' + ''.join(f'<td>{html.escape(str(x))}</td>' for x in [r['contest_date'],
                    c['category'], c['published_unit_eur'], c['reconstructed_unit_eur'] or 'Pendiente de bote previo',
                    'Sí' if c['matches'] else ('No' if c['matches'] is False else 'Sin verificar')]) + '</tr>'
    totals = report['cash_replay']['strategy_totals']
    replay_rows = ''.join('<tr>' + ''.join(f'<td>{html.escape(str(x))}</td>' for x in [name,
        v['contests'], v['cost_eur'], v['gross_eur'], v['net_eur'], f"{v['roi']:.2%}"]) + '</tr>' for name, v in totals.items())
    return '''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Auditoría de premios históricos</title><style>body{font:16px system-ui;background:#f3f5f8;color:#152a3c;margin:0;padding:32px;max-width:1250px;margin:auto}h1{font-size:30px}h2{margin-top:38px}.cards{display:flex;flex-wrap:wrap;gap:14px}article{background:white;border-radius:10px;padding:22px;flex:1;min-width:180px}strong{display:block;font-size:30px}span{display:block}.notice{background:#fff0ce;padding:18px;border-radius:8px;line-height:1.6}table{width:100%;border-collapse:collapse;background:white;font-size:14px}td,th{padding:11px;border-bottom:1px solid #ddd;text-align:left}input{padding:12px;width:240px;margin:14px 0}.scroll{overflow:auto}a{color:#075db3}p,li{line-height:1.6}</style>
<h1>Premios históricos · auditoría económica</h1><p>19 de octubre de 2026 · corte del archivo: domingos del 04/08/2024 al 07/06/2026.</p><div class="cards">''' + cells + '''</div>
<p class="notice">Investigación histórica. La recaudación y los acertantes finales se conocen después de los partidos. Ningún resultado de esta página habilita una recomendación de inversión.</p>
<h2>Qué hemos conseguido</h2><p>Normalizamos las tablas del archivo sin exigir que todos los encuentros pertenezcan a las ligas del predictor. Añadimos cuatro observaciones numéricas de notas oficiales y comparamos dos hipótesis de redondeo. Los casos con bote previo desconocido o reglas excepcionales pendientes quedan visibles.</p>
<h2>Reconstrucción de importes</h2><p>La tabla muestra la hipótesis de redondear primero el fondo a céntimos y después el premio unitario. Es un contraste contable; la convención oficial de redondeo sigue pendiente de confirmación.</p>
<div class="scroll"><table><tr><th>Fecha</th><th>Aciertos</th><th>Publicado €</th><th>Reconstruido €</th><th>Coincide</th></tr>''' + comparisons + '''</table></div>
<h2>Reproducción del experimento histórico</h2><p>Costes y cobros brutos con columnas y signos congelados. Cada estrategia es una alternativa, por lo que sus importes no se suman entre sí. Se conservan las pérdidas.</p>
<div class="scroll"><table><tr><th>Estrategia</th><th>Jornadas</th><th>Coste €</th><th>Cobro €</th><th>Neto €</th><th>ROI histórico bruto</th></tr>''' + replay_rows + '''</table></div>
<h2>Archivo completo de domingos</h2><p>Esta ventana no incluye todos los concursos entre semana. Cero premio y ausencia de acertantes son situaciones distintas. Los cobros sumados usan importes unitarios publicados y sus redondeos.</p>
<input id="filter" aria-label="Filtrar archivo" placeholder="Filtrar por fecha o estado"><div class="scroll"><table id="archive"><thead><tr><th>Fecha</th><th>Estado</th><th>Recaudación €</th><th>Categorías a cero con acertantes</th><th>Sin acertantes</th><th>Pagado bruto publicado €</th></tr></thead><tbody>''' + table + '''</tbody></table></div>
<h2>Datos que siguen faltando</h2><ul><li>Botes efectivamente asignados a cada concurso; la publicidad de un premio máximo no equivale al fondo recibido.</li><li>Recaudación del resto del archivo y confirmación de reglas de redondeo e igualación.</li><li>Porcentajes apostados y estimaciones de recaudación capturados antes del cierre, con fechas verificables.</li><li>Un modelo contrastado de participación conjunta para estimar el número de acertantes futuros.</li></ul>
<p>Las notas fueron observadas con extracción de texto del buscador. La descarga directa devolvió una restricción; los PDF completos no se han archivado. Los registros JSON incluyen procedencia, momento de observación y las lagunas de publicación.</p>
<p><a href="report.json">Informe reproducible JSON</a> · <a href="observations.json">Observaciones numéricas y fuentes</a></p>
<script>document.getElementById('filter').addEventListener('input',e=>{for(const r of document.querySelectorAll('#archive tbody tr'))r.hidden=!r.textContent.toLowerCase().includes(e.target.value.toLowerCase())})</script></html>'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-dir', type=Path, action='append')
    p.add_argument('--observations', type=Path, required=True)
    p.add_argument('--start', default='2024-08-04')
    p.add_argument('--end', default='2026-06-07')
    p.add_argument('--backtest', type=Path, default=ROOT / 'outputs/reports/allocations_v1/report.json')
    p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args()
    if args.output_dir.exists():
        p.error('Choose a new immutable output directory.')
    observations = json.loads(args.observations.read_text(encoding='utf-8'))
    roots = args.raw_dir or [ROOT / 'data/raw/official_expanded', ROOT / 'data/raw/official_coupons']
    rows = audit_archive(roots, date.fromisoformat(args.start), date.fromisoformat(args.end), observations)
    cash = replay(args.backtest, rows)
    summary = {'declared_sundays': len(rows), 'complete_prize_tables': sum(
        r.get('prize_table_complete', False) and r['status'] != 'conflict_or_invalid' for r in rows),
        'status_counts': dict(Counter(r['status'] for r in rows)),
        'revenue_observations': sum(r['revenue_eur'] is not None for r in rows),
        'preclose_economic_records': 0, 'special_carry_in_observations': 0,
        'zero_award_with_winners_contests': sum(bool(r.get('zero_award_categories')) for r in rows)}
    report = {'schema_version': 1, 'created_at': datetime.now(UTC).isoformat(), 'window': [args.start, args.end],
        'summary': summary, 'rows': rows, 'cash_replay': cash, 'economic_deployment_enabled': False,
        'observations_sha256': digest(args.observations), 'script_sha256': digest(Path(__file__)),
        'rules_module_sha256': digest(ROOT / 'src/quantfootball/quiniela/prize_audit.py'),
        'limitations': ['Purposive arithmetic examples, not an unbiased model validation set',
            'Final revenue/winners are post-result inputs; not future ROI estimates',
            'No inferred carry-in is used to validate that same prize',
            'Only ordinary distribution, empty-category transfers and ten-hit suppression supported',
            'Rounding policies are hypotheses; equality and sub-euro upper categories remain blocked',
            'Old extracts have file hashes but no verified capture/publication timestamps',
            'No PDF bytes were archived for new observations; direct downloads were access-restricted']}
    args.output_dir.mkdir(parents=True)
    write(args.output_dir / 'report.json', report)
    write(args.output_dir / 'observations.json', observations)
    (args.output_dir / 'dashboard.html').write_text(render(report), encoding='utf-8')
    print(json.dumps({'summary': summary, 'cash_replay': cash['counts'], 'strategies': cash['strategy_totals']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
