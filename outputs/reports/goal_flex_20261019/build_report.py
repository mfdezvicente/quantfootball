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

NAMES = {'es.1':'Primera masculina','es.2':'Segunda masculina','es.w.1':'Liga F'}
FAMILY = {'poisson':'Poisson de control','independent_nb':'Binomial negativa',
          'shared_tempo':'Ritmo compartido','independent_nb_low':'Binomial negativa + marcadores bajos'}
CAL = {'identity':'Identidad','temperature':'Temperatura','context':'Contextual'}


def explain(label):
    raw,mode = label.split('/')
    if raw == 'reference':
        return 'Referencia previa a calibración · '+CAL[mode]
    family,weight = raw.rsplit('_',1)
    return FAMILY[family]+f' ({float(weight):.0%}) · '+CAL[mode]


def fmt(x):
    return f'{x:.6f}'


def table(headers,rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def write(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--initial',type=Path,required=True)
    args = p.parse_args()
    run = args.run
    report = json.loads((run/'evaluation.json').read_text(encoding='utf-8'))
    initial = json.loads((args.initial/'evaluation.json').read_text(encoding='utf-8'))
    verification = {'all_training_before_cutoff':True,'all_calibration_before_cutoff':True,
        'all_frozen_source_hashes_match':True,'joint_score_metrics_not_inherited_by_1x2_mixtures':True,
        'weekly_fits':0,'stored_variants':0,'production_promotion':False}
    for name,expected in report['protocol']['sources_sha256'].items():
        if hashlib.sha256((run/'source'/name).read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen source changed.')
    headline,contexts,shapes,pleno = [],[],[],[]
    details = ''
    for code,d in report['divisions'].items():
        fits = json.loads((run/f'{code}.fits.json').read_text(encoding='utf-8'))
        for fit in fits:
            if pd.Timestamp(fit['training_last_date']) >= pd.Timestamp(fit['cutoff']) or not fit['converged']:
                raise ValueError('Invalid goal model fit.')
        verification['weekly_fits'] += len(fits)
        selected = d['selected_diagnostic']
        delta = selected['vs_current']
        ci = delta['ci95']
        headline.append([NAMES[code],selected['metrics']['matches'],fmt(d['current_metrics']['log_loss']),
            explain(d['selected_label']),fmt(selected['metrics']['log_loss']),fmt(delta['mean_log_loss_difference']),
            '['+fmt(ci[0])+', '+fmt(ci[1])+']'])
        rankings = json.loads((run/f'{code}.selection.json').read_text(encoding='utf-8'))
        rows = []
        for rank in rankings:
            label = rank['name']+'/'+rank['calibration']
            item = d['all_diagnostics'][label]
            fit = item['calibration_fit']
            if pd.Timestamp(fit['training_last_date']) >= pd.Timestamp(fit['selected_before']):
                raise ValueError('Invalid calibration chronology.')
            variant = pd.read_parquet(run/f"{code}.{rank['name']}.{rank['calibration']}.parquet")
            if any(c.startswith('pleno_') for c in variant):
                raise ValueError('Mixed 1X2 model inherited another score-grid metric.')
            verification['stored_variants'] += 1
            rows.append([explain(label),fmt(rank['metrics']['log_loss']),fmt(item['metrics']['log_loss']),
                         fmt(item['vs_current']['mean_log_loss_difference']),fmt(item['metrics']['brier'])])
        details += '<details><summary>'+NAMES[code]+' · todas las variantes, ordenadas por selección anterior</summary>'+table(['Variante','LL selección 2023–24','LL diagnóstico 2024–26','Δ frente al actual','Brier diagnóstico'],rows)+'</details>'
        for mode in ('identity','temperature','context'):
            item = d['all_diagnostics']['reference/'+mode]
            contexts.append([NAMES[code],CAL[mode],fmt(item['metrics']['log_loss']),
                             fmt(item['vs_current']['mean_log_loss_difference'])])
        for family,shape in report['fits'][code]['shape_by_family'].items():
            shapes.append([NAMES[code],FAMILY[family],f"{shape['median']:.2f}",f"{shape['minimum']:.2f}",f"{shape['maximum']:.2f}"])
        for family,m in d['standalone_goal_metrics'].items():
            pleno.append([NAMES[code],FAMILY[family],fmt(m['one_x_two']['log_loss']),fmt(m['pleno_log_loss']),fmt(m['pleno_brier'])])
    write(run/'verification.json',verification)
    fig,ax = plt.subplots(figsize=(11,4.5))
    for i,(code,d) in enumerate(report['divisions'].items()):
        result = d['selected_diagnostic']['vs_current']
        mean = result['mean_log_loss_difference']
        lower,upper = result['ci95']
        ax.errorbar(mean,i,xerr=[[mean-lower],[upper-mean]],fmt='o',capsize=6,
                    color='#137b80' if mean<0 else '#be5835',markersize=8)
    ax.axvline(0,color='#607d8b',linestyle='--')
    ax.set_yticks(range(3),list(NAMES.values()))
    ax.invert_yaxis()
    ax.set_xlabel('Diferencia de log loss: candidato elegido − modelo actual (menor es mejor)')
    ax.set_title('Diagnóstico 2024–2026 · intervalos exploratorios por semanas')
    ax.grid(axis='x',alpha=.2)
    fig.tight_layout()
    fig.savefig(run/'selected_comparison.png',dpi=160)
    plt.close(fig)
    first_rows = [[NAMES[c],explain(d['selected_label']),fmt(d['current_metrics']['log_loss']),
                   fmt(d['selected_diagnostic']['metrics']['log_loss'])] for c,d in initial['divisions'].items()]
    page = '''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Modelos flexibles de goles y calibración</title>
<style>body{font:16px system-ui;background:#f4f7fa;color:#163044;max-width:1350px;padding:30px;margin:auto}h1{font-size:32px}h2{margin-top:38px}p,li{line-height:1.65}.notice{padding:18px;border-radius:10px;background:#fff0cb}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;background:white;font-size:14px}td,th{padding:11px;border-bottom:1px solid #dce5eb;text-align:left}th{background:#e8eff5}details{padding:16px;background:white;margin:15px 0}img{max-width:100%;height:auto}a{color:#005f92}</style>
<h1>Modelos flexibles de goles y calibración contextual</h1><p>19 de octubre de 2026 · investigación en Primera, Segunda y Liga F.</p>
<p class="notice"><b>Resultado: conservar el modelo actual como referencia.</b> La mejora elegida para Primera es pequeña y su intervalo incluye cero. Los candidatos elegidos para Segunda y Liga F empeoran en el periodo posterior. Estos periodos históricos ya se habían inspeccionado; no son confirmación prospectiva.</p>
<h2>Qué se ha probado</h2><ul><li>Poisson de control, binomial negativa con sobredispersión, ritmo de partido compartido Gamma–Poisson y binomial negativa con una corrección acotada de marcadores bajos.</li><li>Mezclas del 25 %, 50 % y 100 % con la referencia, más la propia referencia.</li><li>Calibración identidad, temperatura y contextual. La contextual usa equilibrio 1X2 y goles esperados, con seis parámetros regularizados.</li></ul>
<p>Los goles se ajustan cada semana con resultados anteriores al corte. La calibración inicial usa 2022–2023; la selección usa 2023–2024. Después se reajusta la calibración con 2022–2024 y se diagnostica en los mismos partidos de 2024–2026. La evaluación final contiene '''+str(verification['weekly_fits'])+''' ajustes de goles convergidos y 39 candidatos por competición.</p>
<h2>Candidatos elegidos con el periodo anterior</h2>'''+table(['Competición','Partidos','LL actual','Candidato elegido','LL candidato','Δ LL','Intervalo exploratorio 95 %'],headline)+'''<img src="selected_comparison.png" alt="Diferencias de log loss e intervalos por competición">
<p>Los intervalos remuestrean semanas y no corrigen la búsqueda entre candidatos ni toda la dependencia entre temporadas y equipos. El candidato elegido se conserva aunque después empeore.</p>
<h2>Qué aporta la calibración contextual</h2><p>Estos modos se aplican a la referencia anterior a su calibración final original. En Liga F, identidad elimina esa calibración original; el valor del modelo actual aparece en la tabla principal. Las mejoras de esta sección son diagnósticas y no eligen una variante con información posterior.</p>'''+table(['Competición','Calibración','LL diagnóstico','Δ frente al modelo actual'],contexts)+'''
<h2>¿Los datos piden más dispersión?</h2><p>En estos modelos, k grande aproxima el límite Poisson. El ajuste llega con frecuencia al límite superior k=1000; los datos y priors de esta prueba apoyan poca sobredispersión adicional. Esto no descarta otras formas de dependencia, variación temporal o errores en las medias.</p>'''+table(['Competición','Familia','k mediano','k mínimo','k máximo'],shapes)+'''
<h2>Todas las variantes</h2>'''+details+'''
<details><summary>Modelos individuales de goles: 1X2 y Pleno 0/1/2/M</summary><p>El Pleno se evalúa como categoría de goles en todos los partidos históricos. Estas métricas pertenecen a cada modelo de goles por separado. Las mezclas y calibraciones 1X2 no heredan una distribución conjunta de marcadores. Las colas de tres o más goles se conservan.</p>'''+table(['Competición','Modelo de goles','LL 1X2','LL categorías Pleno','Brier categorías Pleno'],pleno)+'''</details>
<details><summary>Primera ronda y seguimiento posterior</summary><p>La primera ronda comparó Poisson, binomial negativa y ritmo compartido. Tras revisar sus resultados se planteó la corrección de marcadores bajos. El seguimiento se identifica expresamente como adaptativo y exploratorio; las dos rondas y sus protocolos se conservan.</p>'''+table(['Competición','Elegido en la primera ronda','LL actual','LL diagnóstico del elegido'],first_rows)+'''</details>
<h2>Fuentes y reproducibilidad</h2><p>La investigación de distribuciones y dependencia de goles tiene antecedentes en <a href="https://arxiv.org/abs/2307.02139">Michels, Ötting y Karlis (2023)</a> y <a href="https://doi.org/10.1111/1467-9884.00366">Karlis y Ntzoufras (2003)</a>. Nuestras formulaciones y priors se documentan en el código; no se presenta una réplica de esos estudios.</p>
<p>Se verifican gradientes frente a diferencias numéricas, el modelo de ritmo contra integración Gamma–Poisson, conservación de masa y marginales, colas del Pleno, predicciones sin etiquetas y exclusión de resultados futuros.</p>
<p><a href="evaluation.json">Resultados completos</a> · <a href="protocol.json">Protocolo final</a> · <a href="verification.json">Comprobaciones de ejecución</a> · <a href="initial_round/evaluation.json">Primera ronda conservada</a></p></html>'''
    (run/'dashboard.html').write_text(page,encoding='utf-8')
    notes = ['# Modelos flexibles y calibración contextual — 19 de octubre de 2026','',
        'Investigación histórica de periodos ya inspeccionados. El seguimiento de marcadores bajos se planteó después de ver la primera ronda y es adaptativo.',
        '',f"La evaluación final verifica {verification['weekly_fits']} ajustes semanales convergidos y {verification['stored_variants']} variantes guardadas.",'',
        '| División | Modelo actual LL | Candidato elegido por 2023–24 | LL diagnóstico | Diferencia |','|---|---:|---|---:|---:|']
    for code,d in report['divisions'].items():
        notes.append(f"| {NAMES[code]} | {d['current_metrics']['log_loss']:.6f} | {explain(d['selected_label'])} | {d['selected_diagnostic']['metrics']['log_loss']:.6f} | {d['selected_diagnostic']['vs_current']['mean_log_loss_difference']:+.6f} |")
    notes += ['', 'Primera mejora muy poco y su intervalo incluye cero. Los candidatos elegidos para Segunda y Liga F empeoran. No se cambia el modelo de producción ni el protocolo prospectivo 50/50.',
        '', 'La sobredispersión estimada suele llegar al límite Poisson dentro de las familias y priors ensayados. La calibración contextual da mejoras puntuales de diagnóstico en Primera y Liga F y empeora en Segunda; no se promueve ninguna usando solo estos resultados.',
        '', 'El archivo source/ conserva el código exacto. initial_round/ conserva evaluación, protocolo, selección y código de la primera ronda. Los resultados de Pleno de los modelos de goles se evalúan por separado; las mezclas 1X2 no heredan esos indicadores.',
        '', '## Reproducción', '', 'Usar el entorno del proyecto y una carpeta de salida nueva:', '', '```',
        'python scripts/evaluate_goal_flex_research.py --output-dir outputs/reports/goal_flex_replica --follow-up-to outputs/reports/goal_flex_20261019/initial_round/evaluation.json','```',
        '', '## Límites', *['- '+x for x in report['protocol']['limitations']], '',
        'Los registros antiguos y la configuración congelada de producción se conservan. No se han usado créditos de cuotas ni se demuestra ventaja económica.']
    (run/'REPORT.md').write_text('\n'.join(notes),encoding='utf-8')
    print(json.dumps(verification,indent=2))


if __name__ == '__main__':
    main()
