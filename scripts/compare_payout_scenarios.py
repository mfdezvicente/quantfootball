"""Compare frozen portfolios under explicitly hypothetical prize tables."""

import argparse
import hashlib
import html
import json
from datetime import UTC, datetime
from pathlib import Path

from quantfootball.quiniela.payout_scenarios import payout_scenario


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forecast", type=Path, required=True)
    parser.add_argument("--prize-scenarios", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    forecast = json.loads(args.forecast.read_text(encoding="utf-8"))
    specification = json.loads(args.prize_scenarios.read_text(encoding="utf-8"))
    if specification.get("purpose") != "hypothetical_sensitivity" or not specification.get("limitations"):
        raise ValueError("Explicit hypothetical_sensitivity purpose and limitations are required.")
    scenarios = specification["scenarios"]
    if not 1 <= len(scenarios) <= 20 or len({s["name"] for s in scenarios}) != len(scenarios):
        raise ValueError("Use one to twenty distinctly named scenarios.")
    if len(forecast["coupons"]) != 1:
        raise ValueError("Use one frozen coupon.")
    coupon = forecast["coupons"][0]
    if len(coupon["fixtures"]) != 14:
        raise ValueError("A full fourteen-match forecast is required.")
    point = [[r[k] for k in ("p_home", "p_draw", "p_away")] for r in coupon["fixtures"]]
    results, table = [], []
    for budget, plans in coupon["budgets"].items():
        for scenario in scenarios:
            for name, plan in plans["strategies"].items():
                result = payout_scenario(point, plan["columns"], scenario["prizes_by_hits"], plan["cost_eur"])
                results.append({"budget": budget, "scenario": scenario["name"], "strategy": name, **result})
                table.append("<tr>" + "".join(f"<td>{html.escape(str(x))}</td>" for x in (
                    scenario["name"], name, f'{result["cost_eur"]:.2f} €',
                    f'{result["probability_any_cash"]:.2%}',
                    f'{result["probability_recover_stake"]:.2%}',
                    f'{result["probability_profit"]:.2%}',
                    f'{result["conditional_expected_net_eur"]:.2f} €',
                )) + "</tr>")
    files = [args.forecast, args.prize_scenarios, Path(__file__),
             Path(__file__).resolve().parents[1] / "src/quantfootball/quiniela/payout_scenarios.py",
             Path(__file__).resolve().parents[1] / "src/quantfootball/quiniela/risk.py",
             Path(__file__).resolve().parents[1] / "src/quantfootball/quiniela/coverage.py"]
    report = {"created_at": datetime.now(UTC).isoformat(), "status": "hypothetical_not_prospective_validation",
              "inputs": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
              "specification": specification, "results": results}
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    limitations = "".join(f"<li>{html.escape(str(x))}</li>" for x in specification["limitations"])
    page = '''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
    <title>Cobrar, recuperar y ganar</title><style>body{font:16px system-ui;margin:32px;background:#f4f7fa;color:#17293b}
    table{border-collapse:collapse;background:white}td,th{padding:12px;border-bottom:1px solid #ccd5dd;text-align:left}
    .notice{padding:20px;background:#fff0ce;max-width:1050px}section{overflow-x:auto}li{margin:8px 0}</style>
    <h1>Cobrar, recuperar el gasto y obtener beneficio</h1>
    <p class="notice"><strong>Escenarios hipotéticos: no prueban rentabilidad futura.</strong>
    Se conservan las probabilidades y las columnas originales. Los premios se fijan por escenario.
    La media económica es condicional a esos supuestos y puede depender de premios muy raros.
    No incluye Pleno, impuestos, cambios de recaudación ni del número de acertantes.</p>
    <ul>''' + limitations + '''</ul><section><table><thead><tr><th>Premios</th><th>Estrategia</th><th>Coste</th>
    <th>P(cobrar)</th><th>P(recuperar gasto)</th><th>P(beneficio)</th><th>Neto medio condicionado</th></tr></thead>
    <tbody>''' + "".join(table) + '''</tbody></table></section><p>Las columnas comparten resultados:
    se calcula el cobro conjunto, incluyendo varios premios pequeños simultáneos.
    Exacto bajo independencia entre partidos; sin ajuste de columnas a resultados observados.</p></html>'''
    (args.output_dir / "dashboard.html").write_text(page, encoding="utf-8")
    print(json.dumps({"output": str(args.output_dir), "comparisons": len(results)}))


if __name__ == "__main__":
    main()
