"""Render a local HTML report; no web server or external assets needed."""

import argparse
import json
from pathlib import Path

from quantfootball.quiniela.dashboard import render_dashboard


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--form-evaluation", type=Path)
    a = parser.parse_args()
    report, evaluation, audit = [
        json.loads(p.read_text(encoding="utf-8")) for p in (a.report, a.evaluation, a.audit)
    ]
    if a.form_evaluation:
        evaluation["form_experiment"] = json.loads(a.form_evaluation.read_text(encoding="utf-8"))
    render_dashboard(report, evaluation, audit, a.output)
    print(a.output)


if __name__ == "__main__":
    main()
