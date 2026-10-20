"""Render the read-only actual odds/model benchmark without any ticket purchase."""

import json
from pathlib import Path


def render_market_study(report, output):
    template = Path(__file__).with_suffix(".html").read_text(encoding="utf-8")
    payload = json.dumps(report, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    with Path(output).open("x", encoding="utf-8") as handle:
        handle.write(template.replace("__PAYLOAD__", payload))
