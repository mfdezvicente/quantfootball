"""Build a read-only project continuation report from immutable evidence."""
import argparse
import hashlib
import html
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from quantfootball.data.active import inspect_inputs, resolve_active
from quantfootball.market.match_study import evaluate_studies, verify_study
from quantfootball.market.prospective import evaluate_pairs


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--report-dir', type=Path, required=True)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.report_dir.resolve()
    active = resolve_active(root)
    future_dir = root/'outputs/predictions/market_matches/20261028_pre_round'
    seal, future = verify_study(future_dir)
    provisional = read(root/'outputs/predictions/j18_preliminary_20261028/forecast.json')
    observation = read(out/'j18_inputs/provisional_observation.json')
    payout = read(out/'j14_hypothetical_returns.json')
    coverage = read(out/'current_season_coverage.json')
    snapshots = out/'public_results'
    market = evaluate_studies(root/'outputs/predictions/market_matches', active['dataset'],
                              sporting_snapshots=snapshots)
    legacy = evaluate_pairs(root/'outputs/predictions/probability_pairs', active['dataset'],
                            sporting_snapshots=snapshots)
    pool = evaluate_pairs(root/'outputs/predictions/probability_pairs_pool50', active['dataset'],
                          sporting_snapshots=snapshots)
    for name, value in [('market_evaluation.json',market),('legacy_probability_evaluation.json',legacy),
                        ('pool50_probability_evaluation.json',pool)]:
        save(out/name,value)
    cutoff='2026-10-28'
    preflight=inspect_inputs(active['dataset'],active['config'],cutoff,active['max_result_age_days'])
    quota=read(root/'data/raw/market_the_odds_api/20261028/audit.json')
    # League schedules confirm identities, dates and kickoff instants independently of coupon order.
    by_key={ (f['competition_code'],f['home_team'],f['away_team'],f['date'][:10]):f
              for f in future['fixtures'] }
    schedule_errors=[]
    for f in observation['fixtures'][:14]:
        k=(f['competition_code'],f['home_team'],f['away_team'],f['date'])
        if f['competition_code']=='es.w.1':continue
        quoted=by_key.get(k)
        if quoted is None or datetime.fromisoformat(quoted['starts_at'])!=datetime.fromisoformat(f['starts_at']):
            schedule_errors.append(f['position'])
    coupon=provisional['coupons'][0]
    report={
      'created_at':datetime.now(UTC).isoformat(), 'paper_only':True,
      'inputs':preflight,'current_season_coverage':coverage,
      'observed_financial_evidence':payout,'market_evaluation':market,
      'legacy_probability_evaluation':legacy,'pool50_probability_evaluation':pool,
      'new_match_study':{'registered_at':seal['registered_at'],'matched_fixtures':future['comparison']['matched_fixtures'],
                         'by_competition':dict(Counter(f['competition_code'] for f in future['fixtures'])),
                         'seal_sha256':digest(future_dir/'seal.json'),'scope':seal['scope']},
      'next_coupon':{'contest_id':'2026_j18','observation':observation,'ready_to_register':False,
                     'blockers':['official_coupon_order_unverified'],
                     'men_schedule_mismatches':schedule_errors,
                     'provisional_forecast_sha256':digest(root/'outputs/predictions/j18_preliminary_20261028/forecast.json'),
                     'forecast_draws':coupon['model']['bootstrap_draws'],
                     'budget_eur':10,'economic_action':'abstain','recommended_stake_eur':0},
      'odds_capture':{'credits_used':quota['reported_credit_cost_successful_requests'],
                      'remaining':quota['remaining_after_last_success'], 'errors':quota['errors']},
      'missed_prospective_contests':[{'contest_id':c,'reason':'No verified pre-close paired registration',
                                    'retroactive_record_created':False} for c in ['2026_j14','2026_j16']],
      'expected_roi':None,'positive_expected_roi_demonstrated':False,
      'limitations':['No verified J18 coupon order; closing time alone is insufficient to register the ticket',
                     'J14 return is hypothetical on archived unregistered columns; no purchase or prospective ROI',
                     'J16 has no frozen forecast to score as a prospective model decision',
                     'No women odds; observations are not replaced with invented market estimates',
                     'Only 24 unique completed market pairs; 21 new predictions await results',
                     'Local seals and Git history do not certify a purchased bet or external trusted timestamp']}
    if schedule_errors:report['next_coupon']['blockers'].append('market_schedule_mismatch')
    save(out/'report.json',report)
    def e(value):return html.escape(str(value))
    def euro(value):return f'{value:.2f}'.replace('.',',')+' €'
    payrows=''.join(f'<tr><td>{e(name)}</td><td>{euro(row["cost_eur"])}</td><td>{e(row["hit_counts"])}</td><td>{euro(row["gross_return_eur"])}</td><td class="loss">{euro(row["net_eur"])}</td></tr>' for name,row in payout['strategies'].items())
    metricrows=''.join(f'<tr><td>{e(code)}</td><td>{row["paired_matches"]}</td><td>{row["model"]["log_loss"]:.4f}</td><td>{row["market"]["log_loss"]:.4f}</td></tr>' for code,row in market['leagues'].items())
    fixtures=''
    for forecast,obs in zip(coupon['fixtures'],observation['fixtures']):
        p=[forecast[k] for k in ['p_home','p_draw','p_away']]
        fixtures+=f'<tr><td>{obs["position"]}</td><td>{e(obs["home_team"])} — {e(obs["away_team"])}</td><td>{e(obs["competition_code"])}</td>'+''.join(f'<td>{v:.1%}</td>' for v in p)+'</tr>'
    body=f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>QuantFootball · avances del 28 de octubre</title>
<style>body{{font:16px/1.55 system-ui;background:#f2f5f8;color:#172b3a;max-width:1150px;margin:36px auto;padding:0 22px}}h1{{line-height:1.2}}h2{{margin-top:32px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}}.card,section{{background:white;border:1px solid #d9e1e8;padding:20px;border-radius:12px}}.card b{{display:block;font-size:28px}}.notice{{background:#fff1d5;padding:16px;border-left:4px solid #bd7600}}.loss{{color:#9e2837;font-weight:700}}.tag{{font-size:13px;color:#53697b}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{text-align:left;padding:9px;border-bottom:1px solid #dde4e9}}.scroll{{overflow:auto}}a{{color:#0764a5}}small{{color:#52677a}}</style>
<h1>QuantFootball · actualización del 28 de octubre de 2026</h1><p>Datos nuevos, liquidación hipotética de J14 y captura anterior a los próximos partidos. Simulación; ventaja económica sin demostrar.</p>
<div class="grid"><div class="card"><b>{preflight['rows']:,}</b>partidos · +32 resultados</div><div class="card"><b>{future['comparison']['matched_fixtures']}</b>nuevos partidos con modelo y cuotas sellados</div><div class="card"><b>{market['completed_unique_fixtures']}</b>comparaciones previas terminadas</div><div class="card"><b>0 €</b>importe económico recomendado</div></div>
<h2>J14: resultado observado y retorno hipotético</h2><section><p class="tag">RESULTADOS Y PREMIOS PUBLICADOS · CARTERAS SIN COMPRA VERIFICADA</p><p>El premio de diez fue <b>0 €</b>; el de once, <b>2,22 €</b>. La cartera de trece columnas habría cobrado <b>6,66 €</b> sobre un coste de 9,75 €: pérdida de <b>3,09 €</b>. El sistema completo habría perdido sus 9 €.</p><div class="scroll"><table><tr><th>Cartera guardada</th><th>Coste</th><th>Columnas por aciertos</th><th>Cobro</th><th>Neto</th></tr>{payrows}</table></div><p><a href="{e(payout['source']['source_url'])}">Escrutinio primario SELAE J14</a>. Se conserva el pronóstico original y no se añade este retorno a la cohorte prospectiva.</p></section>
<h2>Modelo y mercado sobre los mismos partidos</h2><section><p class="tag">RESULTADOS OBSERVADOS · MUESTRA TODAVÍA PEQUEÑA</p><table><tr><th>Competición</th><th>Partidos</th><th>Log loss modelo</th><th>Log loss mercado</th></tr>{metricrows}</table><p>Un valor menor es mejor. El mercado conserva ventaja en esta muestra. Hay 21 nuevos pronósticos anteriores al inicio pendientes de resultado. No se modifica el modelo para corregir una sola jornada.</p><p><a href="../../predictions/market_matches/20261028_pre_round/dashboard.html">Abrir nuevo estudio sellado</a>.</p></section>
<h2>J18 · preparación para el 1 de noviembre</h2><section><p class="tag">ESTIMACIONES PREVIAS · ORDEN DEL BOLETO PROVISIONAL</p><p class="notice"><b>Cierre oficial: sábado 31 de octubre a las 14:00, hora de Madrid.</b> Sigue pendiente verificar la composición oficial del boleto. La descarga del ZIP de SELAE devolvió HTTP 403; no se ha eludido la restricción. La J18 aún no está registrada como pareja del experimento 50/50.</p><p>Los quince cruces y horarios se han cotejado con LaLiga. Los diez cruces masculinos de las primeras catorce posiciones también coinciden con las cuotas actuales. Liga F conserva el modelo propio porque no hay cuotas disponibles.</p><div class="scroll"><table><tr><th>Nº provisional</th><th>Partido</th><th>Liga</th><th>P(1)</th><th>P(X)</th><th>P(2)</th></tr>{fixtures}</table></div><p>Se han calculado 64 remuestreos y carteras hasta 10 €. <a href="../../predictions/j18_preliminary_20261028/dashboard.html">Explorar sistemas y columnas provisionales</a>. La dispersión de esos remuestreos es sensibilidad del estimador y no una garantía de aciertos.</p><p><a href="{e(observation['closing_source_url'])}">Aviso oficial del cierre</a>.</p></section>
<h2>Mejoras del flujo y siguiente decisión</h2><section><ul><li>El cruce de resultados comprueba ahora que el registro precede al inicio real, también si el horario cambió dentro del mismo día.</li><li>El actualizador antiguo exige entradas y una salida nuevas; ya no puede sobrescribir silenciosamente el snapshot histórico.</li><li>Se ha contrastado la cobertura de 32 jornadas de las tres ligas: están incorporados todos los resultados finales elegibles observados; el partido abandonado permanece excluido.</li><li>J14 y J16 siguen visibles como concursos sin nueva pareja prospectiva. No se reconstruyen decisiones a posteriori.</li></ul><p>Para el siguiente registro hace falta confirmar el orden oficial de J18 y comprobar de nuevo las cuotas y el plazo. La mezcla 50/50 mantiene su protocolo de 5 €; el seguimiento termina el 1 de julio de 2027. El estudio por partidos conserva su cohorte propia.</p><p>La estimación de ROI esperado continúa pendiente de participación conjunta y premios contrastados. Hasta entonces, la acción económica es abstenerse.</p></section><p><small>Fuente de datos activos: snapshot 28-10-2026; resultados hasta el 26 en hombres y hasta el 25 en Liga F. El informe conserva JSON, auditorías y procedencia. Captura de cuotas: 2 créditos; saldo reportado {quota['remaining_after_last_success']}.</small></p></html>'''
    with (out/'dashboard.html').open('x',encoding='utf-8') as f:f.write(body)
    print(json.dumps({'ready':preflight['ready'],'rows':preflight['rows'],'new_market_pairs':future['comparison']['matched_fixtures'],
                     'schedule_mismatches':schedule_errors,'pool50_records':len(pool['records']),
                     'report':str(out/'dashboard.html')},indent=2))


if __name__=='__main__':
    main()
