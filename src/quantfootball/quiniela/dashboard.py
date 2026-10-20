"""Self-contained Spanish HTML explorer for forecasts and historical diagnostics."""

import json
from pathlib import Path


def render_dashboard(report: dict, evaluation: dict, audit: dict, output: Path):
    template = Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")
    payload = json.dumps(
        {"report": report, "evaluation": evaluation, "audit": audit},
        ensure_ascii=False,
        allow_nan=False,
    ).replace("<", "\\u003c")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(template.replace("__PAYLOAD__", payload))
