import json,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
root=Path(__file__).resolve().parent
sys.path.insert(0,'C:/Users/Usuario/GitHub/quantfootball/scripts')
from fetch_ligaf import fetch
output=root/'public_results'
output.mkdir(exist_ok=False)
def capture(item):
 code,week=item
 try:
  record=fetch(2026,week,output,code)
  return {'code':code,'week':week,'results':record['matches']}
 except Exception as exc:
  return {'code':code,'error':str(exc)}
with ThreadPoolExecutor(max_workers=3) as executor:
 for value in executor.map(capture,[('es.1',9),('es.2',10),('es.w.1',7)]):
  print(json.dumps(value,ensure_ascii=False),flush=True)
