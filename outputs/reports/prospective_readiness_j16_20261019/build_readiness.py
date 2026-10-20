import hashlib
import html
import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from quantfootball.market.snapshots import key

STAGE = Path(__file__).resolve().parent
sources = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((STAGE / 'public_schedule').glob('*.json'))]
by_code = {c: next(s for s in sources if slug in s['source_url']) for c, slug in
           [('es.1', 'laliga-easports'), ('es.2', 'laliga-hypermotion'), ('es.w.1', 'futbol-femenino')]}
# Provisional order transcribed from two independent secondary listings.
selection = [('es.1', 14), ('es.1', 18), ('es.1', 2), ('es.1', 3), ('es.1', 6),
             ('es.1', 16), ('es.1', 17), ('es.2', 54), ('es.2', 1), ('es.2', 38),
             ('es.w.1', 390), ('es.w.1', 406), ('es.w.1', 387), ('es.w.1', 904), ('es.1', 4)]
fixtures = []
for position, (code, home_id) in enumerate(selection, 1):
    source = by_code[code]
    matches = [m for m in source['matches'] if m['home_team_id'] == home_id]
    assert len(matches) == 1, (code, home_id)
    match = matches[0]
    row = {'position': position, 'competition_code': code, 'gender': 'women' if code == 'es.w.1' else 'men',
           'home_team': match['home_team'], 'away_team': match['away_team'],
           'starts_at': match['date'], 'date': datetime.fromisoformat(match['date']).astimezone(ZoneInfo('Europe/Madrid')).date().isoformat(),
           'schedule_source_url': source['source_url'], 'schedule_captured_at': source['fetched_at'],
           'source_match_id': match['id']}
    _, row['home_team'], row['away_team'] = key(row)
    fixtures.append(row)
obs = {'contest_id': '2026_j16', 'captured_at': datetime.now(UTC).isoformat(), 'is_example': False,
       'official_order_verified': False, 'closes_at': None,
       'source_url': 'https://quiniprats.com/es/quiniela/2026-27/jornada/16',
       'secondary_crosscheck_url': 'https://www.quinielafutbol.info/proximas-jornadas-de-la-quiniela.html',
       'label': 'J16 — preparación provisional; cierre y orden oficial pendientes', 'fixtures': fixtures}
(STAGE / 'provisional_observation.json').write_text(json.dumps(obs, ensure_ascii=False, indent=2), encoding='utf-8')
(STAGE / 'fixtures_14.json').write_text(json.dumps(fixtures[:14], ensure_ascii=False, indent=2), encoding='utf-8')
(STAGE / 'pleno.json').write_text(json.dumps(fixtures[14], ensure_ascii=False, indent=2), encoding='utf-8')
readiness = {'created_at': obs['captured_at'], 'contest_id': obs['contest_id'], 'ready_to_register': False,
             'blockers': ['official_coupon_order_unverified', 'official_close_unverified', 'current_odds_not_captured'],
             'schedule_matches_confirmed': 15, 'predictions_registered': False, 'economic_decision_registered': False,
             'api_credits_used': 0, 'credential_file_present': True, 'credential_decryption_tested': False,
             'source_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (STAGE / 'public_schedule').glob('*.json')},
             'limitations': 'League schedules confirm matches and times, not official coupon inclusion/order or betting deadline.'}
(STAGE / 'readiness.json').write_text(json.dumps(readiness, ensure_ascii=False, indent=2), encoding='utf-8')
rows = ''.join('<tr><td>%s</td><td>%s</td><td>%s – %s</td><td>%s</td></tr>' %
    (r['position'], r['competition_code'], html.escape(r['home_team']), html.escape(r['away_team']),
     datetime.fromisoformat(r['starts_at']).astimezone(ZoneInfo('Europe/Madrid')).strftime('%d/%m %H:%M %z')) for r in fixtures)
page = '''<!doctype html><html lang="es"><meta charset="utf-8"><title>Preparación J16</title>
<style>body{font:17px system-ui;max-width:1050px;margin:40px auto;padding:20px;background:#f4f6f8;color:#142635}table{border-collapse:collapse;width:100%;background:white}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}.notice{padding:18px;background:#fff0cf;border-radius:8px}</style>
<h1>J16 · preparación del registro</h1><p>Captura: 19 de octubre de 2026. Horas de Madrid, con cambio de hora el domingo.</p>
<p class="notice"><strong>Pendiente de registro.</strong> Falta confirmar oficialmente el orden del boleto y su cierre, y capturar cuotas actuales. Esta pantalla no contiene una apuesta recomendada.</p>
<p>Los 15 cruces se han contrastado con calendarios de LaLiga. El orden procede de fuentes secundarias y sigue siendo provisional. No se han consumido créditos de cuotas.</p>
<table><tr><th>Posición provisional</th><th>Liga</th><th>Partido</th><th>Inicio Madrid</th></tr>''' + rows + '''</table>
<h2>Corrección aplicada al ciclo</h2><p>Primero se generan probabilidades reales del modelo; después se comparan con las cuotas y se comprueba de nuevo el plazo. Se bloquean ejemplos, cuotas caducadas o ausentes y se conservan diagnósticos de fallos.</p>
<p>La mezcla 50/50 mantiene su protocolo de 5 €. La estrategia económica sigue sin evidencia suficiente para recomendar jugar.</p>
<p>Fuentes de orden provisional: <a href="https://quiniprats.com/es/quiniela/2026-27/jornada/16">QuiniPrats</a> y <a href="https://www.quinielafutbol.info/proximas-jornadas-de-la-quiniela.html">QuinielaFutbol</a>.</p></html>'''
(STAGE / 'dashboard.html').write_text(page, encoding='utf-8')
print(json.dumps([(r['position'], r['home_team'], r['away_team']) for r in fixtures], ensure_ascii=False))
