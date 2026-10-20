import json,hashlib
from pathlib import Path
from collections import Counter
import numpy as np,pandas as pd
from quantfootball.data.teams import canonicalize_team
from quantfootball.data.competitions import women_team_name
from quantfootball.market.prospective import verify_pair
from quantfootball.quiniela.registry import registry_summary,verify_record
root=Path('C:/Users/Usuario/GitHub/quantfootball'); out=Path.cwd()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
dataset=root/'data/processed/matches_quiniela_20261014.parquet'; data=pd.read_parquet(dataset)
summary={'dataset':{'file':str(dataset),'rows':len(data),'sha256':hashlib.sha256(dataset.read_bytes()).hexdigest(),'divisions':{code:{'matches':len(g),'first_date':str(g.date.min()),'last_date':str(g.date.max()),'seasons':int(g.season.nunique()),'current_season_matches':int((g.season=='2026-27').sum())} for code,g in data.groupby('competition_code')}},'registry':registry_summary(root/'outputs/predictions/registry'),'probability_pair_records':[],'economic_records':[],'pool50_records':[]}
for p in sorted((root/'outputs/predictions/probability_pairs').iterdir()):
 if p.is_dir():
  try: seal,values=verify_pair(p); summary['probability_pair_records'].append({'id':p.name,'valid':True,'registered_at':seal['registered_at']})
  except Exception as e: summary['probability_pair_records'].append({'id':p.name,'valid':False,'reason':str(e)})
for name,key in [('economic_decisions','economic_records'),('probability_pairs_pool50','pool50_records')]:
 p=root/'outputs/predictions'/name
 summary[key]=[x.name for x in p.iterdir() if x.is_dir()] if p.exists() else []
forecast_path=root/'outputs/predictions/j14_preliminary_10eur_20261015/forecast.json'; forecast=read(forecast_path); coupon=forecast['coupons'][0]
lookup={}
for p in (out/'public_results').glob('*.json'):
 capture=read(p); code= 'es.w.1' if 'es.w.1' in p.name else 'es.2' if 'es.2' in p.name else 'es.1'
 norm=women_team_name if code=='es.w.1' else canonicalize_team
 for m in capture['matches']:
  k=(code,norm(m['home_team']),norm(m['away_team']))
  assert k not in lookup
  lookup[k]={**m,'source_url':capture['source_url'],'captured_at':capture['fetched_at']}
rows=[]
for f in coupon['fixtures']:
 code=f['competition_code']; norm=women_team_name if code=='es.w.1' else canonicalize_team
 key=(code,norm(f['home_team']),norm(f['away_team']))
 m=lookup[key]; assert m['id']==f['schedule_match_id'] and m['status']=='FullTime'
 sign='1' if m['home_score']>m['away_score'] else '2' if m['home_score']<m['away_score'] else 'X'
 prob=[f[n] for n in ['p_home','p_draw','p_away']]; target=['1','X','2'].index(sign)
 y=np.eye(3)[target]
 rows.append({'position':f['position'],'competition_code':code,'home_team':f['home_team'],'away_team':f['away_team'],'score':f"{m['home_score']}-{m['away_score']}",'sign':sign,'probabilities':prob,'favorite':['1','X','2'][int(np.argmax(prob))],'log_loss':float(-np.log(prob[target])),'brier':float(np.sum((prob-y)**2)),'source_url':m['source_url']})
strategies={}
for name,s in coupon['budgets']['10.00']['strategies'].items():
 hits=[sum(pick==r['sign'] for pick,r in zip(c['signs'],rows)) for c in s['columns']]
 strategies[name]={'column_count':s['column_count'],'cost_eur':s['cost_eur'],'hits':hits,'max_hits':max(hits),'predicted_P14':s['coverage'],'predicted_P10':s['risk']['at_least']['10'],'predicted_P11':s['risk']['at_least']['11']}
metrics={}
for code in ['all','es.1','es.2','es.w.1']:
 r=[x for x in rows if code=='all' or x['competition_code']==code]
 metrics[code]={'matches':len(r),'log_loss':sum(x['log_loss'] for x in r)/len(r),'brier':sum(x['brier'] for x in r)/len(r),'favorite_accuracy':sum(x['sign']==x['favorite'] for x in r)/len(r)}
pleno=coupon['pleno']; m=lookup[(pleno['competition_code'],canonicalize_team(pleno['home_team']),canonicalize_team(pleno['away_team']))]
summary['j14']={'forecast_file':str(forecast_path),'forecast_sha256':hashlib.sha256(forecast_path.read_bytes()).hexdigest(),'created_at':forecast['created_at'],'registration_status':forecast['registration_status'],'prospective_financial_roi_eligible':False,'metrics':metrics,'strategies':strategies,'fixtures':rows,'pleno':{'status':m['status'],'source_url':m['source_url'],'captured_at':m['captured_at']},'accounting':'Sporting diagnostic of saved unregistered preparation. No official awarded signs or payouts obtained; no realized investment ROI.'}
summary['inventory']={'python_modules':len(list((root/'src/quantfootball').rglob('*.py'))),'scripts':len(list((root/'scripts').glob('*.py'))),'test_files':len(list((root/'tests').glob('test_*.py')))}
(out/'audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='j14'},ensure_ascii=False,indent=2))
print('J14',json.dumps({'metrics':metrics,'strategies':strategies,'pleno':summary['j14']['pleno']},ensure_ascii=False,indent=2))
