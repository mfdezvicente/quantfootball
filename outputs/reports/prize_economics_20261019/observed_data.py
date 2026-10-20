"""Numeric facts observed via web text extraction, not full PDF reproductions."""
from datetime import UTC, datetime

BASE = 'https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Notas%20de%20prensa/'
EXAMPLES = [
    ('2024-08-04', 'NOTA_DE_PRENSA_LA_QUINIELA_4_08_24.pdf', '528911.25',
     [(0, None), (0, None), (0, '0.00'), (7, '11333.81'), (131, '302.81'), (1046, '45.51')], '2024-08-04'),
    ('2025-04-13', 'NOTA_DE_PRENSA_LA_QUINIELA_13_04_25.pdf', '3613179.75',
     [(0, None), (2, '289054.38'), (82, '3304.74'), (1304, '207.81'), (11489, '23.59'), (67588, '4.81')], '2025-04-14'),
    ('2026-05-24', 'NOTA_DE_PRENSA_LA_QUINIELA_24_05_26.pdf', '3980005.50',
     [(0, None), (0, None), (29, '10293.12'), (421, '709.03'), (4560, '65.46'), (30540, '11.73')], '2026-05-24'),
    ('2026-06-07', 'NOTA_DE_PRENSA_LA_QUINIELA_07_06_26.pdf', '1079358.75',
     [(6, '13491.99'), (62, '2785.44'), (1229, '65.87'), (10577, '7.65'), (49422, '1.64'), (143387, '0.00')], '2026-06-08'),
]


def observations():
    return [{'contest_date': day, 'source_url': BASE + filename, 'revenue_eur': revenue,
             'prizes': {k: {'winners': n, 'unit_eur': u} for k, (n, u) in zip(('15','14','13','12','11','10'), prizes)},
             'captured_at': datetime.now(UTC).isoformat(), 'observation_method': 'primary_web_tool_text_numeric_transcription',
             'full_pdf_archived': False, 'publication_timestamp': None, 'document_date': docday,
             'special_carry_in_eur': None, 'preclose_evidence': False,
             'selection_note': 'Purposive rule-branch examples, not a representative ROI sample.'}
            for day, filename, revenue, prizes, docday in EXAMPLES]
