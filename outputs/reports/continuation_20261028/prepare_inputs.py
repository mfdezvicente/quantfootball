from pathlib import Path
from datetime import UTC,datetime
from zoneinfo import ZoneInfo
from collections import Counter
import json,hashlib
import pandas as pd
from quantfootball.market.snapshots import key
from quantfootball.quiniela.settlement import settle_columns

ROOT=Path(r'C:\Users\Usuario\GitHub\quantfootball')
STAGE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

rows=[]
selection=[('es.1',11,11),('es.1',11,14),('es.1',11,5),('es.1',11,4),
 ('es.1',11,9),('es.1',11,49),('es.1',11,7),('es.2',12,27),
 ('es.2',12,962),('es.2',12,53),('es.w.1',9,516),('es.w.1',9,329),
 ('es.w.1',9,328),('es.w.1',9,239),('es.1',11,3)]
for position,(code,week,home_id) in enumerate(selection,1):
 p=STAGE/'public_results'/f'2026-{code}-{week:02}.json';source=read(p)
 match=[m for m in source['matches'] if m['home_team_id']==home_id]
 if len(match)!=1:raise ValueError('Ambiguous fixture')
 m=match[0]
 row={'position':position,'competition_code':code,'gender':'women' if code=='es.w.1' else 'men',
      'home_team':m['home_team'],'away_team':m['away_team'],'starts_at':m['date'],
      'date':datetime.fromisoformat(m['date']).astimezone(ZoneInfo('Europe/Madrid')).date().isoformat(),
      'source_match_id':m['id'],'schedule_source_url':source['source_url'],
      'schedule_captured_at':source['fetched_at']}
 _,row['home_team'],row['away_team']=key(row)
 rows.append(row)
obs={'contest_id':'2026_j18','captured_at':datetime.now(UTC).isoformat(),'is_example':False,
     'official_order_verified':False,'official_close_verified':True,'closes_at':'2026-10-31T14:00:00+01:00',
     'source_url':'https://www.loteriadealicante.es/la-quiniela-directo/',
     'secondary_crosscheck_url':'https://www.quinielafutbol.info/proximas-jornadas-de-la-quiniela.html',
     'closing_source_url':'https://www.selae.es/f/loterias/web_corporativa/Comunicacion/Avisos_de_interes/Aviso%20cierre%20La%20Quiniela%20jornada%2018%C2%AA%20y%20El%20QuiniGol%20jornada%2019%C2%AA%20de%2031%20Octubre%20-%201%20Noviembre%20de%202026.pdf',
     'closing_source_method':'Primary PDF text and image observed via web tool; direct archive HTTP403',
     'label':'J18 · preparación provisional; orden oficial pendiente','fixtures':rows}
for name,value in [('provisional_observation.json',obs),('fixtures_14.json',rows[:14]),('pleno.json',rows[14])]:
 save(STAGE/'j18_inputs'/name,value)

prizes14={str(k):{'winners':w,'unit_eur':v} for k,w,v in [
 (15,18,'80778.13'),(14,50,'11162.13'),(13,1583,'165.26'),(12,20502,'12.76'),(11,117869,'2.22'),(10,371994,'0.00')]}
prizes16={str(k):{'winners':w,'unit_eur':v} for k,w,v in [
 (15,0,None),(14,15,'36053.45'),(13,557,'455.12'),(12,6862,'36.94'),(11,45227,'5.61'),(10,186259,'1.63')]}
observations=[]
for num,date,signs,pleno,prizes in [(14,'18','2X2X121X211121','1-1',prizes14),
                                   (16,'25','2211X11XXX11X1','1-2',prizes16)]:
 observations.append({'contest_id':f'2026_j{num}','nominal_date':f'2026-10-{date}',
  'source_url':f'https://www.loteriasyapuestas.es/es/la-quiniela/escrutinios/la-quiniela-premios-y-ganadores-del-{date}-de-octubre-de-2026',
  'observed_via':'Primary page extraction by web tool; full direct archive HTTP403',
  'recorded_at':datetime.now(UTC).isoformat(),'publication_date_shown':f'2026-10-{int(date)+1:02}',
  'publication_time_verified':False,'awarded_signs':signs,'pleno_actual':pleno,'prizes':prizes,
  'gross_revenue_eur':None,'carry_in_eur':None,
  'note':'A zero displayed with no Pleno winners is kept as unknown unit payout, not an estimated counterfactual jackpot.'})
save(STAGE/'official_observations.json',observations)

forecast_path=ROOT/'outputs/predictions/j14_preliminary_10eur_20261015/forecast.json'
report=read(forecast_path);coupon=report['coupons'][0]
out={'created_at':datetime.now(UTC).isoformat(),'contest_id':'2026_j14','prospective':False,
     'actual_purchase_verified':False,'original_forecast_sha256':sha(forecast_path),
     'source':observations[0],'strategies':{},'scope':'Hypothetical return on archived unregistered columns; excluded from prospective cohort.'}
for name,plan in next(iter(coupon['budgets'].values()))['strategies'].items():
 paid=settle_columns(plan['columns'],list(observations[0]['awarded_signs']),prizes14,
                     pleno_prediction=coupon['pleno']['prediction'],pleno_actual='1-1')
 paid['hit_counts']={str(k):v for k,v in Counter(paid['column_hits']).items()}
 out['strategies'][name]=paid
save(STAGE/'j14_hypothetical_returns.json',out)

frame=pd.read_parquet(STAGE/'matches_quiniela_20261028.parquet')
current=frame[frame.season.eq('2026-27')]
coverage=[]
for p in sorted((STAGE/'public_results').glob('2026-es.*-*.json')):
 r=read(p);code=p.name.split('-')[1]
 # Match source identities against the full current-season dataset, independently of old matchday labels.
 known={key(row) for row in current[current.competition_code.eq(code)].to_dict('records')}
 eligible=[m for m in r['matches'] if m['status']=='FullTime' and
           datetime.fromisoformat(m['date']).astimezone(ZoneInfo('Europe/Madrid')).date().isoformat()<'2026-10-28']
 missing=[]
 for m in eligible:
  if key({'competition_code':code,'gender':'women' if code=='es.w.1' else 'men',
          'home_team':m['home_team'],'away_team':m['away_team']}) not in known:
   missing.append({'home_team':m['home_team'],'away_team':m['away_team']})
 coverage.append({'competition_code':code,'matchday':r['matchday'],'source_matches':len(r['matches']),
                  'final_eligible':len(eligible),'missing_final_results':missing,
                  'statuses':dict(Counter(m['status'] for m in r['matches']))})
save(STAGE/'current_season_coverage.json',{'created_at':datetime.now(UTC).isoformat(),'rounds':coverage,
 'all_observed_final_results_present':all(not c['missing_final_results'] for c in coverage),
 'scope':'32 public rounds captured; not a certificate about unseen or changed provider records.'})
print(json.dumps({'rows':len(frame),'current_season_rows':current.competition_code.value_counts().to_dict(),
                  'missing_final_results':sum(len(c['missing_final_results']) for c in coverage),
                  'j14_returns':{k:(v['cost_eur'],v['gross_return_eur'],v['net_eur']) for k,v in out['strategies'].items()}},indent=2))
