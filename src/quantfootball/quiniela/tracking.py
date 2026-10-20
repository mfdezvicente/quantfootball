"""Read-only consolidated paper ledger. Never merge hypothetical and observed ROI."""

import html
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from quantfootball.quiniela.decision import ECONOMIC_BLOCKERS, verify_decision
from quantfootball.quiniela.payout_scenarios import cents
from quantfootball.quiniela.registry import digest, registry_summary


def performance(entries):
    """Chronological settled-only ledger; moving blocks retain adjacent contests."""
    settled = sorted((r for r in entries if r["status"] == "settled"), key=lambda r: (r["closes_at"], r["record"]))
    costs = np.array([cents(r["settlement"]["cost_eur"]) for r in settled], dtype=float)
    gross = np.array([cents(r["settlement"]["gross_return_eur"]) for r in settled], dtype=float)
    equity = np.r_[0, np.cumsum(gross - costs)]
    total = float(costs.sum())
    result = {
        "settled_count": len(settled), "settled_cost_eur": total / 100,
        "settled_gross_eur": float(gross.sum()) / 100,
        "net_eur": float(equity[-1]) / 100,
        "observed_roi": float(gross.sum() / total - 1) if total else None,
        "maximum_drawdown_eur": float((np.maximum.accumulate(equity) - equity).max()) / 100,
        "largest_prize_share_of_gross": float(gross.max() / gross.sum()) if gross.sum() else None,
        # Remove the best payout while retaining its stake: dependence-on-jackpot stress.
        "roi_without_largest_payout": float((gross.sum() - gross.max()) / total - 1) if total else None,
        "equity_eur": (equity / 100).tolist(), "ordered_contests": [r["record"] for r in settled],
        "roi_block_bootstrap_95": None,
        "complete_accounting": all(r["status"] in ("settled", "abstain") for r in entries),
        "interpretation": "Paper, settled only; pending stakes excluded from ROI and separately visible. No proof of edge.",
    }
    if len(settled) >= 8 and total:
        n, length = len(settled), min(4, len(settled))
        rng = np.random.default_rng(20261014)
        starts = rng.integers(0, n - length + 1, size=(5000, (n + length - 1) // length))
        indices = (starts[:, :, None] + np.arange(length)).reshape(5000, -1)[:, :n]
        bootstrap_cost = costs[indices].sum(axis=1)
        roi = gross[indices].sum(axis=1) / bootstrap_cost - 1
        result["roi_block_bootstrap_95"] = np.quantile(roi, [.025, .975]).tolist()
        result["bootstrap_note"] = "5000 moving-block resamples, four adjacent settled contests; exploratory, not unseen-tail coverage"
    return result


def consolidated_report(legacy_root, decision_root, *, evidence_files=None):
    legacy_root, decision_root = Path(legacy_root), Path(decision_root)
    legacy = registry_summary(legacy_root)
    entries, fingerprints = [], {}
    for entry in legacy["records"]:
        entry = dict(entry)
        folder = legacy_root / entry["record"]
        entry["cohort"] = "legacy_coverage"
        entry["path"] = str(folder.resolve())
        if entry["status"] != "invalid":
            seal = json.loads((folder / "seal.json").read_text(encoding="utf-8"))
            entry["closes_at"] = seal["closes_at"]
            entry["registered_at"] = seal["registered_at"]
            report = json.loads((folder / "forecast.json").read_text(encoding="utf-8"))
            coupon = report["coupons"][0]
            strategy = next(iter(coupon["budgets"].values()))["strategies"][seal["primary_strategy"]]
            entry["stake_eur"] = strategy["cost_eur"]
            entry["coverage_estimate"] = strategy.get("risk")
            entry["market_available"] = bool(coupon.get("market_comparison"))
            entry["forecast_inputs"] = report.get("inputs")
            entry["model"] = report.get("config")
            for path in folder.glob("*.json"):
                fingerprints[str(path.resolve())] = digest(path)
        entries.append(entry)
    for folder in sorted(decision_root.iterdir()) if decision_root.exists() else []:
        if not folder.is_dir():
            continue
        try:
            decision = verify_decision(folder)
            entry = {**decision, "record": folder.name, "status": "abstain", "cohort": "economic_v1"}
            for path in folder.glob("*.json"):
                fingerprints[str(path.resolve())] = digest(path)
        except (ValueError, KeyError, OSError, TypeError) as exc:
            entry = {"record": folder.name, "status": "invalid", "reason": str(exc), "cohort": "economic_v1"}
        entries.append(entry)
    evidence = {}
    for name, path in (evidence_files or {}).items():
        if path is None:
            continue
        path = Path(path)
        evidence[name] = json.loads(path.read_text(encoding="utf-8"))
        fingerprints[str(path.resolve())] = digest(path)
    return {
        "schema_version": 1, "created_at": datetime.now(UTC).isoformat(),
        "paper_only": True, "economic_readiness": {"action": "abstain", "blockers": ECONOMIC_BLOCKERS,
            "maximum_budget_eur": 10, "not_a_registered_contest_decision": True},
        "entries": entries, "legacy_summary": legacy,
        "cohorts": {c: performance([r for r in entries if r["cohort"] == c])
                    for c in ("legacy_coverage", "economic_v1")},
        "inputs_sha256": fingerprints, "expected_positive_roi_demonstrated": False,
        "evidence": evidence,
    }


def render_tracking(report, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    rows = []
    for entry in report["entries"]:
        values = [entry["record"], entry["cohort"], entry["status"], entry.get("stake_eur", "—"),
                  entry.get("settlement", {}).get("gross_return_eur", "—"),
                  ", ".join(entry.get("reason_codes", [])) or entry.get("reason", "")]
        rows.append("<tr>" + "".join("<td>" + html.escape(str(v)) + "</td>" for v in values) + "</tr>")
    def table(headers, values):
        head = "".join("<th>" + html.escape(v) + "</th>" for v in headers)
        body = "".join("<tr>" + "".join("<td>" + html.escape(str(v)) + "</td>" for v in row) + "</tr>" for row in values)
        return "<section><table><tr>" + head + "</tr>" + body + "</table></section>"
    metrics = []
    for name, cohort in report["cohorts"].items():
        roi = cohort["observed_roi"]
        metrics.append(["Cobertura anterior" if name == "legacy_coverage" else "Decisiones económicas",
                        cohort["settled_count"], f'{cohort["settled_cost_eur"]:.2f}',
                        "Pendiente" if roi is None else f"{roi:.2%}",
                        "Sin datos" if not cohort["settled_count"] else f'{cohort["maximum_drawdown_eur"]:.2f} €'])
    page = '''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
    <title>QuantFootball · Seguimiento económico</title><style>
    body{font:16px system-ui;background:#f3f6fa;color:#172b3e;margin:32px;max-width:1300px}
    .notice{background:#fff0cc;padding:20px;border-radius:12px}table{background:white;border-collapse:collapse;width:100%}
    td,th{padding:12px;border-bottom:1px solid #d4dce4;text-align:left}section{overflow-x:auto}pre{white-space:pre-wrap}
    </style><h1>Seguimiento económico · Simulación</h1><div class="notice"><strong>Estado: evidencia insuficiente para recomendar jugar.</strong>
    <p>Máximo 10 € por jornada. No hay compra automática. Faltan modelos validados de participación conjunta y premios,
    y un protocolo económico prospectivo. Este estado general no equivale a una abstención registrada antes de una jornada.</p></div>
    <h2>Decisiones y liquidaciones</h2><p>Las cohortes de cobertura y economía permanecen separadas.
    Los pendientes no se convierten en pérdidas ni en premios cero. Las liquidaciones secundarias no entran en el ROI oficial.</p>
    <section><table><tr><th>Jornada</th><th>Cohorte</th><th>Estado</th><th>Gasto €</th><th>Cobro €</th><th>Motivo</th></tr>'''
    page += "".join(rows) + "</table></section><h2>Resultados observados</h2>"
    page += table(["Cohorte", "Jornadas liquidadas", "Gasto liquidado €", "ROI observado", "Caída máxima"], metrics)
    evidence = report.get("evidence", {})
    if "probability_evaluation" in evidence:
        evaluation = evidence["probability_evaluation"]
        page += "<h2>Estimaciones previas · Calidad probabilística</h2><p>"
        page += f'{evaluation["completed_unique_fixtures"]} partidos deportivos evaluados; {evaluation["sporting_excluded_unique_fixtures"]} exclusión deportiva. '
        page += "Estas métricas no calculan rentabilidad.</p>"
        page += table(["Competición", "Partidos", "Log loss candidato", "Brier candidato"],
                      [[code, data["matches"], f'{data["candidate"]["log_loss"]:.4f}',
                        f'{data["candidate"]["brier"]:.4f}'] for code, data in evaluation["leagues"].items()])
    if "market_evaluation" in evidence:
        evaluation = evidence["market_evaluation"]
        page += "<h2>Comparación con cuotas por partido</h2><p>Comparación distinta del registro económico del boleto: "
        page += f'{evaluation["completed_unique_fixtures"]} partidos únicos. Algunos snapshots se capturaron después del cierre de su boleto; '
        page += "sirven para comparar predicciones anteriores al partido, no para reconstruir decisiones anteriores al cierre.</p>"
        page += table(["Competición", "Partidos", "Log loss modelo", "Log loss mercado"],
                      [[code, data["paired_matches"], f'{data["model"]["log_loss"]:.4f}',
                        f'{data["market"]["log_loss"]:.4f}'] for code, data in evaluation["leagues"].items()])
    if "research_evaluation" in evidence:
        page += "<h2>Investigación retrospectiva · Ascensos y calendario</h2><p>Se elige usando 2022–2024 y se diagnostica en "
        page += "2024–2026, temporadas ya inspeccionadas. Ninguna variante sustituye al modelo actual.</p>"
        research_rows = []
        for code, data in evidence["research_evaluation"]["divisions"].items():
            for name, value in data["diagnostics"].items():
                research_rows.append([code, name, value["metrics"]["matches"], f'{value["metrics"]["log_loss"]:.4f}',
                                      f'{value["vs_incumbent"]["mean_log_loss_difference"]:+.4f}'])
        page += table(["Competición", "Variables", "Partidos", "Log loss", "Diferencia con modelo actual (+ empeora)"], research_rows)
    if "source_audit" in evidence:
        page += "<h2>Datos económicos · Disponibilidad</h2>"
        page += table(["Fuente", "Estado", "Carencia"], [[r["name"], r["status"], r["gap"]]
                      for r in evidence["source_audit"]["items"]])
    page += '''<h2>Cómo interpretar el panel</h2><ul><li>Resultado observado: liquidaciones verificadas del registro simulado.</li>
    <li>Estimación previa: probabilidades congeladas antes del cierre; no son promesas de cobro.</li>
    <li>Escenario hipotético: sensibilidad a premios supuestos; se excluye de todas las rentabilidades observadas.</li>
    <li>Sin suficientes jornadas liquidadas, la incertidumbre económica permanece sin estimar.</li></ul></html>'''
    (output / "dashboard.html").write_text(page, encoding="utf-8")
