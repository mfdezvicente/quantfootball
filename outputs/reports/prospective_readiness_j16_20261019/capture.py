import importlib.util
from pathlib import Path

ROOT = Path('C:/Users/Usuario/GitHub/quantfootball')
out = Path(__file__).resolve().parent / 'public_schedule'
out.mkdir(exist_ok=True)
spec = importlib.util.spec_from_file_location('fetch', ROOT / 'scripts/fetch_ligaf.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
for code, week in [('es.1', 10), ('es.2', 11), ('es.w.1', 8)]:
    mod.fetch(2026, week, out, code)
