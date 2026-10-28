"""Capture current season coverage from the original public league pages."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import UTC, datetime
import importlib.util
import json
import time

ROOT = Path(r'C:\Users\Usuario\GitHub\quantfootball')
OUT = Path(__file__).resolve().parent / 'public_results'
OUT.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location('league_fetch', ROOT/'scripts/fetch_ligaf.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def capture(item):
    code, end = item
    records = []
    for week in range(1, end + 1):
        try:
            record = mod.fetch(2026, week, OUT, code)
            records.append({'file': f'2026-{code}-{week:02}.json', 'matches': len(record['matches']),
                            'status': 'captured'})
        except Exception as exc:
            records.append({'competition_code': code, 'matchday': week, 'status': 'failed',
                            'error_type': type(exc).__name__, 'reason': str(exc)})
            if getattr(getattr(exc, 'response', None), 'status_code', None) in (401,403,429):
                break
        time.sleep(0.25)
    return records

with ThreadPoolExecutor(max_workers=3) as pool:
    batches = list(pool.map(capture, [('es.1',11), ('es.2',12), ('es.w.1',9)]))
audit = {'created_at': datetime.now(UTC).isoformat(), 'records': sum(batches, []),
         'purpose': 'Full current-season coverage audit; only final pre-cutoff rows may enter training.'}
(OUT/'capture_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print(json.dumps({'captured':sum(x['status']=='captured' for x in audit['records']),
                  'failures':[x for x in audit['records'] if x['status']!='captured']}),flush=True)
