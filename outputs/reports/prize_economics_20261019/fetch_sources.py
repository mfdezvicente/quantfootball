"""One capture per explicitly reviewed, accessible official PDF; no retries/mirrors."""
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent / 'sources'
ROOT.mkdir(exist_ok=True)
BASE = 'https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Notas%20de%20prensa/'
DOCUMENTS = {
    '2024-08-04': 'NOTA_DE_PRENSA_LA_QUINIELA_4_08_24.pdf',
    '2025-04-13': 'NOTA_DE_PRENSA_LA_QUINIELA_13_04_25.pdf',
    '2026-05-24': 'NOTA_DE_PRENSA_LA_QUINIELA_24_05_26.pdf',
    '2026-06-07': 'NOTA_DE_PRENSA_LA_QUINIELA_07_06_26.pdf',
}
for day, filename in DOCUMENTS.items():
    target = ROOT / f'{day}.json'
    if target.exists():
        continue
    url = BASE + filename
    response = requests.get(url, timeout=40)
    captured = datetime.now(UTC).isoformat()
    if response.status_code != 200 or not response.content.startswith(b'%PDF'):
        target.write_text(json.dumps({'url': url, 'captured_at': captured,
            'status': 'unavailable_no_retry', 'http_status': response.status_code,
            'final_url': response.url}, indent=2), encoding='utf-8')
        print(day, 'unavailable; no retry')
        continue
    pdf = ROOT / f'{day}.pdf'
    pdf.write_bytes(response.content)
    reader = PdfReader(io.BytesIO(response.content))
    text = '\n'.join(page.extract_text(extraction_mode='layout') for page in reader.pages)
    (ROOT / f'{day}.txt').write_text(text, encoding='utf-8')
    target.write_text(json.dumps({'url': url, 'captured_at': captured,
        'status': 'primary_pdf_captured', 'pdf_sha256': hashlib.sha256(response.content).hexdigest(),
        'contest_date_asserted': day, 'publication_timestamp': None,
        'publication_note': 'Document calendar date is not a verified publication timestamp.',
        'pages': len(reader.pages), 'extraction': 'pypdf layout'}, indent=2), encoding='utf-8')
    print(day, len(reader.pages), 'pages captured')
