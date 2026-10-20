"""Present retrospective diagnostics and controlled ablations with explicit limits."""
import argparse
import hashlib
import html
import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use('Agg')
from matplotlib import pyplot as plt

from quantfootball.data.active import resolve_active
from quantfootball.models.calibration import calibrate_probabilities
from quantfootball.research.diagnostics import (
    PROBS,
    attach_roster_flags,
    metrics,
    paired_delta,
)

ROOT = Path('C:/Users/Usuario/GitHub/quantfootball')
NAMES = {'es.1':'Primera masculina','es.2':'Segunda masculina','es.w.1':'Liga F'}
GROUP_NAMES = {'base':'Modelo actual','opponents':'Rivales: rendimiento ajustado',
    'dynamic':'Ataque y defensa: estados dinámicos','rest':'Tiempo desde el último partido conocido',
    'congestion':'Congestión de liga','transfer':'Cambios de división'}
SEGMENT_NAMES = {'favorites_ge_70pct':'Favoritos con probabilidad ≥70 %',
    'promoted_from_es2':'Partidos con ascendidos de Segunda',
    'new_to_covered_leagues':'Partidos con clubes sin temporada previa en las ligas cubiertas'}


def fmt(x):
    return '—' if x is None else f'{x:.5f}'


def table(headers,rows):
    return '<div class="scroll"><table><thead><tr>' + ''.join(f'<th>{html.escape(str(v))}</th>' for v in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{html.escape(str(v))}</td>' for v in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def write_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False,
                               default=lambda o:o.isoformat() if isinstance(o,pd.Timestamp) else str(o)),encoding='utf-8')


def component_study(archive,config):
    """Isolate archived dynamic goal component; same fixed final calibrator."""
    out = {}
    for code in NAMES:
        baseline = pd.read_parquet(archive/f'dynamic_calibration_v1/{code}.incumbent.parquet')
        baseline = baseline[pd.to_datetime(baseline.date) >= '2024-07-01'].copy()
        raw = pd.read_parquet(archive/f'dynamic_calibration_v1/{code}.raw.parquet')
        raw = raw[raw.candidate.eq(1)].set_index('match_id').reindex(baseline.match_id)
        if raw[PROBS].isna().any().any() or not np.array_equal(raw.result,baseline.result):
            raise ValueError('Dynamic component fixtures/results mismatch.')
        current = pd.read_parquet(archive/f'dynamic_calibration_v1/{code}.selected.parquet')
        current = current.set_index('match_id').reindex(baseline.match_id).reset_index()
        fits = json.loads((archive/f'dynamic_calibration_v1/{code}.fits.json').read_text(encoding='utf-8'))
        selected_fits = [f for f in fits if f['candidate'] == 1]
        if any(pd.Timestamp(f['training_last_date']) >= pd.Timestamp(f['cutoff']) for f in selected_fits):
            raise ValueError('A cached dynamic fit reaches its prediction cutoff.')
        variants = {}
        for weight in (0,.25,.5):
            frame = baseline.copy()
            p = (1-weight)*baseline[PROBS].to_numpy()+weight*raw[PROBS].to_numpy()
            frame[PROBS] = calibrate_probabilities(p,config['divisions'][code]['calibration'])
            if weight == config['divisions'][code]['dynamic_weight']:
                if not np.allclose(frame[PROBS],current[PROBS],atol=1e-9,rtol=0):
                    raise ValueError('Current dynamic component does not reproduce stored incumbent.')
            variants[str(weight)] = {'metrics':metrics(frame),'vs_current':paired_delta(frame,current)}
        out[code] = {'current_weight':config['divisions'][code]['dynamic_weight'],'variants':variants,
            'cached_fits':len(selected_fits), 'cached_fits_converged':sum(f['converged'] for f in selected_fits),
            'note':'Additional descriptive component check using cached strictly prior weekly fits; no validation ranking or weight selection from these diagnostic scores.'}
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run',type=Path,required=True)
    args = p.parse_args()
    run = args.run
    report = json.loads((run/'evaluation.json').read_text(encoding='utf-8'))
    active = resolve_active(ROOT)
    data = pd.read_parquet(active['dataset'])
    config = json.loads(active['config'].read_text(encoding='utf-8'))
    audit = {'monthly_fits_verified': 0, 'paired_predictions_verified': 0,
             'all_training_labels_before_coefficient_cutoff': True,
             'frozen_source_hashes_match': True, 'production_promotion': False}
    for name,expected in report['protocol']['source_sha256'].items():
        frozen = run/'source'/name
        if not frozen.exists() or hashlib.sha256(frozen.read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen research source does not match the declared protocol.')
    for code,division in report['divisions'].items():
        base = pd.read_parquet(run/f'{code}.base.parquet').set_index('match_id')
        for name,variant in division['variants'].items():
            candidate = pd.read_parquet(run/f'{code}.{name}.parquet').set_index('match_id')
            if set(candidate.index) != set(base.index) or not candidate.result.reindex(base.index).equals(base.result):
                raise ValueError('A variant is not evaluated on the exact same labelled fixtures.')
            audit['paired_predictions_verified'] += len(candidate)
            for fit in variant['fits']:
                if pd.Timestamp(fit['training_last_date']) >= pd.Timestamp(fit['coefficient_cutoff']):
                    raise ValueError('A classifier fit includes labels at or after its coefficient cutoff.')
                audit['monthly_fits_verified'] += 1
    write_json(run/'verification.json',audit)
    components = component_study(ROOT/'outputs/reports',config)
    write_json(run/'dynamic_component_diagnostic.json',components)
    write_json(run/'report_provenance.json',{'report_builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'dynamic_cache_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT/'outputs/reports/dynamic_calibration_v1').glob('*.parquet')}})
    segments = {}
    for code,division in report['divisions'].items():
        baseline = attach_roster_flags(pd.read_parquet(run/f'{code}.base.parquet'),data)
        baseline = baseline[baseline.date >= '2024-07-01']
        groups = {'promoted_from_es2': baseline.promoted_from_es2.to_numpy(),
                  'new_to_covered_leagues':baseline.new_to_covered_leagues.to_numpy(),
                  'favorites_ge_70pct':baseline[PROBS].max(axis=1).to_numpy() >= .7,
                  'actual_draws_descriptive':baseline.result.eq('D').to_numpy()}
        segments[code] = {}
        for name in division['variants']:
            frame = pd.read_parquet(run/f'{code}.{name}.parquet')
            frame = frame[pd.to_datetime(frame.date) >= '2024-07-01'].set_index('match_id').reindex(baseline.match_id).reset_index()
            segments[code][name] = {label:{'matches':int(mask.sum()),
                'candidate':metrics(frame.loc[mask]), 'baseline':metrics(baseline.loc[mask]),
                'delta':paired_delta(frame.loc[mask],baseline.loc[mask])}
                for label,mask in groups.items() if mask.any()}
    write_json(run/'segment_comparisons.json',segments)
    fig, axes = plt.subplots(1,3,figsize=(14,4.5),sharex=True,sharey=True)
    for ax,(code,title) in zip(axes,NAMES.items()):
        bins = report['diagnostics'][code]['class_calibration']['D']
        kept = [b for b in bins if b['matches'] > 0]
        ax.plot([0,1],[0,1],color='#8899aa',linestyle='--',linewidth=1)
        ax.scatter([b['mean_probability'] for b in kept],[b['observed_frequency'] for b in kept],
                   s=[15+np.sqrt(b['matches'])*5 for b in kept],color='#126782')
        for b in kept:
            ax.annotate(str(b['matches']),(b['mean_probability'],b['observed_frequency']),xytext=(4,5),textcoords='offset points',fontsize=8)
        ax.set(title=title,xlabel='Probabilidad prevista de empate',xlim=(0,.65),ylim=(0,.65))
        ax.grid(alpha=.2)
    axes[0].set_ylabel('Frecuencia observada de empate')
    fig.suptitle('Calibración histórica de empates · 2024–2026 · etiquetas = partidos por intervalo')
    fig.tight_layout()
    fig.savefig(run/'draw_calibration.png',dpi=160)
    plt.close(fig)
    baseline_rows = []
    for code,diagnostic in report['diagnostics'].items():
        m = diagnostic['overall']
        baseline_rows.append([NAMES[code],m['matches'],fmt(m['log_loss']),fmt(m['brier']),
            f"{m['accuracy']:.1%}",f"{m['mean_draw_probability']:.1%}",f"{m['observed_draw_rate']:.1%}"])
    market_rows = []
    for code,item in report['paired_market']['leagues'].items():
        if item['paired_matches'] == 0:
            market_rows.append([NAMES[code],0,'Sin cuotas archivadas','—','—'])
        else:
            market_rows.append([NAMES[code],item['paired_matches'],fmt(item['model']['overall']['log_loss']),
                fmt(item['market']['overall']['log_loss']),fmt(item['pool50_retrospective']['overall']['log_loss'])])
    sections = ''
    for code,division in report['divisions'].items():
        rows = []
        for name,item in division['variants'].items():
            ci = item['vs_base']['ci95']
            rows.append([GROUP_NAMES[name],item['feature_count'],fmt(item['selection_metrics']['log_loss']),
                         fmt(item['diagnostic_metrics']['log_loss']),fmt(item['vs_base']['mean_log_loss_difference']),
                         '—' if ci is None else '['+fmt(ci[0])+', '+fmt(ci[1])+']',fmt(item['diagnostic_metrics']['brier'])])
        sections += '<h3>'+NAMES[code]+'</h3><p>Mejor resultado en el periodo de selección: <b>'+GROUP_NAMES[division['selection_winner']]+'</b>. El intervalo describe el remuestreo de semanas y no corrige la selección repetida de modelos.</p>'
        sections += table(['Variante','Variables del clasificador','LL 2022–24','LL 2024–26','Δ LL frente a base','Intervalo exploratorio 95 %','Brier 2024–26'],rows)
    component_rows = []
    for code,study in components.items():
        for weight,item in study['variants'].items():
            component_rows.append([NAMES[code],weight,fmt(item['metrics']['log_loss']),fmt(item['vs_current']['mean_log_loss_difference'])])
    errors = ''
    for code,item in report['diagnostics'].items():
        worst = [[str(r['date'])[:10],r.get('home_team','')+' – '+r.get('away_team',''),
                  {'H':'1','D':'X','A':'2'}[r['result']],
                  ' / '.join(f"{r[c]:.1%}" for c in PROBS),fmt(r['loss'])] for r in item['worst_15'][:8]]
        errors += '<details><summary>'+NAMES[code]+' · mayores errores históricos</summary>'+table(['Fecha','Partido','Resultado 1X2','P(1) / P(X) / P(2)','Log loss'],worst)+'</details>'
    facts = []
    for code,item in report['diagnostics'].items():
        for label in ('favorites_ge_70pct','promoted_from_es2','new_to_covered_leagues'):
            m = item['segments'][label]
            if m['matches']:
                facts.append([NAMES[code],SEGMENT_NAMES[label],m['matches'],fmt(m['log_loss']),f"{m['accuracy']:.1%}"])
    page = '''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Diagnóstico y experimentos del predictor</title>
<style>body{font:16px system-ui;color:#172d3e;background:#f3f6f9;max-width:1300px;margin:auto;padding:30px}h1{font-size:32px}h2{margin-top:38px}p,li{line-height:1.65}.notice{padding:20px;background:#fff0cb;border-radius:10px}.scroll{overflow:auto}table{border-collapse:collapse;background:white;width:100%;font-size:14px}td,th{padding:12px;border-bottom:1px solid #dce4eb;text-align:left}th{background:#e8eff5}img{max-width:100%;height:auto;background:white}a{color:#005c9e}details{background:white;padding:16px;margin:16px 0}</style>
<h1>Diagnóstico y experimentos controlados</h1><p>19 de octubre de 2026 · Primera, Segunda y Liga F.</p>
<p class="notice"><b>Investigación retrospectiva.</b> Los periodos históricos ya se habían inspeccionado. Estas diferencias sirven para escoger qué investigar; cualquier cambio de modelo necesita una evaluación prospectiva propia. El protocolo 50/50 y el predictor actual se conservan.</p>
<h2>1. Diagnóstico del modelo actual</h2><p>Log loss penaliza especialmente equivocarse con mucha confianza. En log loss y Brier, un valor menor indica mejores probabilidades.</p>''' + table(['Competición','Partidos','Log loss ↓','Brier ↓','Acierto favorito','Empate previsto','Empate observado'],baseline_rows) + '''<p>Los promedios de empate cercanos no garantizan buena calibración en todos los rangos. El gráfico muestra tamaños de muestra y la frecuencia observada por intervalo.</p><img src="draw_calibration.png" alt="Calibración de empates por liga con número de partidos">
<h2>2. Modelo y mercado sobre los mismos partidos</h2>''' + table(['Competición','Partidos emparejados','LL modelo','LL mercado','LL mezcla 50/50 retrospectiva'],market_rows) + '''<p>Se verifica el sellado de los estudios y se conserva el primer registro por encuentro. Se excluye el partido abandonado. La comparación de mercado contiene pocas jornadas, por lo que no se presenta un intervalo que sugiera una precisión injustificada. La mezcla de esta tabla es un cálculo retrospectivo.</p>''' + errors + '''
<h2>3. Una variable cambia cada vez</h2><p>El clasificador de Primera sigue siendo boosting; el de Segunda, regresión logística. Ambos se entrenan con las dos ligas, como en el sistema original, con coeficientes mensuales y resultados anteriores al corte. El peso del clasificador en la probabilidad final permanece en el 25 %. Se reproduce el clasificador original en tres cortes para verificar la compatibilidad con el archivo.</p>''' + sections + '''
<details><summary>Qué significan las nuevas variables</summary><ul><li>Rivales: puntos obtenidos frente a los esperados por la fuerza previa de cada oponente.</li><li>Dinámica: estados de ataque y debilidad defensiva actualizados con los errores de goles esperados en partidos anteriores; es una aproximación de variables, no el modelo dinámico completo.</li><li>Descanso: tiempo desde el último resultado conocido al corte hasta la fecha programada.</li><li>Congestión: encuentros de liga conocidos en ventanas de 7, 14 y 28 días.</li><li>División: continuidad de la categoría y proporción de encuentros recientes en otra división.</li></ul><p>El calendario utiliza fechas históricas finales y solo partidos de liga. No incluye Copa, Europa, bajas o xG ni certifica cuándo se publicaron los horarios.</p></details>
<h2>4. Componente de goles dinámicos</h2><p>Comprobación adicional sobre las mismas predicciones semanales archivadas, manteniendo la calibración final y cambiando solo el peso del modelo dinámico completo de precisión 48. Son diagnósticos históricos sin selección de peso para producción.</p>''' + table(['Competición','Peso dinámico','LL 2024–26','Δ LL frente al modelo actual'],component_rows) + '''
<h2>5. Segmentos que conviene vigilar</h2>''' + table(['Competición','Segmento','Partidos','Log loss','Acierto favorito'],facts) + '''<p>Los ascendidos a Primera se identifican por participación anterior en Segunda. «Nuevo en ligas cubiertas» también puede indicar falta de historial; no equivale automáticamente a ascenso confirmado. Las diferencias entre segmentos pueden reflejar rivales y dificultad distintos.</p>
<p><a href="evaluation.json">Resultados completos</a> · <a href="diagnostics.json">Diagnóstico y peores errores</a> · <a href="segment_comparisons.json">Comparaciones dentro de los mismos segmentos</a> · <a href="protocol.json">Protocolo de investigación</a></p></html>'''
    (run/'dashboard.html').write_text(page,encoding='utf-8')
    notes = ['# Diagnóstico y experimentos controlados del predictor','',
        'Investigación retrospectiva de periodos ya inspeccionados; no constituye una mejora prospectiva ni evidencia de ROI.',
        '', '## Resultado por división']
    for code,division in report['divisions'].items():
        notes += ['',NAMES[code]+': selección = '+division['selection_winner']+'.']
        for name,item in division['variants'].items():
            notes.append(f"- {name}: LL selección {item['selection_metrics']['log_loss']:.6f}; diagnóstico {item['diagnostic_metrics']['log_loss']:.6f}; delta {item['vs_base']['mean_log_loss_difference']:+.6f}; intervalo {item['vs_base']['ci95']}.")
    notes += ['', '## Límites', *['- '+x for x in report['protocol']['limitations']], '',
        'Ningún modelo de producción, configuración congelada o registro anterior se ha modificado. Las diferencias de este informe no habilitan recomendaciones económicas.']
    (run/'REPORT.md').write_text('\n'.join(notes),encoding='utf-8')
    print(json.dumps({code:{'selection':d['selection_winner'],'diagnostic':d['diagnostic_winner_descriptive_only'],
        'deltas':{n:x['vs_base']['mean_log_loss_difference'] for n,x in d['variants'].items()}} for code,d in report['divisions'].items()},indent=2))


if __name__ == '__main__':
    main()
