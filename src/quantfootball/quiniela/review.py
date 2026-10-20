"""Read-only sporting review of frozen first-14 paper portfolios."""

import html
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

from quantfootball.data.results import ResultLookup
from quantfootball.market.prospective import digest, verify_pair


def review_pair(record, dataset):
    seal, values = verify_pair(record)
    candidate, _comparator, observation, protocol = values
    coupon = candidate["coupons"][0]
    lookup = ResultLookup(pd.read_parquet(dataset))
    stamp = datetime.fromisoformat(seal["registered_at"])
    pack = next(iter(coupon["budgets"].values()))
    strategies = pack["strategies"]
    selections = strategies["full_system"]["selections"]
    fixtures, actual = [], []
    for index, fixture in enumerate(coupon["fixtures"]):
        result = lookup.find(fixture, stamp)
        sign = ("1", "X", "2")[result["target"]] if result else None
        actual.append(sign)
        fixtures.append({"position": fixture["position"], "competition_code": fixture["competition_code"],
                         "home_team": fixture["home_team"], "away_team": fixture["away_team"],
                         "forecast_date": fixture["date"][:10], "selection": selections[index],
                         "probabilities": [fixture[k] for k in ("p_home", "p_draw", "p_away")],
                         "actual_sign": sign, "score": f"{int(result['home_goals'])}-{int(result['away_goals'])}" if result else None,
                         "actual_date": result["actual_date"] if result else None,
                         "result_match_method": result["result_match_method"] if result else None,
                         "source_url": result["source_url"] if result else None,
                         "covered": sign in selections[index] if sign else None})
    pending = actual.count(None)
    audits = {}
    for name, strategy in strategies.items():
        columns = strategy["columns"]
        known = [sum(sign == played for sign, played in zip(col["signs"], actual) if played is not None)
                 for col in columns]
        best_lower, best_upper = max(known), max(known) + pending
        price = Decimal(".75") * len(columns)
        if len({tuple(c["signs"]) for c in columns}) != len(columns) or Decimal(str(strategy["cost_eur"])) != price:
            raise ValueError("Frozen portfolio has invalid column inventory or cost.")
        impossible = best_upper < 10
        audits[name] = {"column_count": len(columns), "cost_eur": float(price), "known_column_hits": known,
                       "best_hits_lower_bound": best_lower, "best_hits_upper_bound": best_upper,
                       "sporting_10_plus_impossible": impossible,
                       "conditional_gross_return_eur": 0.0 if impossible else None,
                       "conditional_net_eur": -float(price) if impossible else None,
                       "conditional_roi": -1.0 if impossible else None,
                       "condition": "Assuming official first-14 awarded signs equal the final sporting results"}
    return {"schema_version": 1, "contest_id": observation["contest_id"],
            "created_at": datetime.now(UTC).isoformat(), "prediction_registered_at": seal["registered_at"],
            "prediction_seal_sha256": digest(Path(record) / "seal.json"), "dataset_sha256": digest(dataset),
            "completed_fixtures": 14 - pending, "pending_fixtures": pending,
            "sporting_status": "complete" if pending == 0 else "pending_results",
            "official_settlement_status": "pending_official_awarded_signs_and_prizes",
            "primary_strategy": protocol["primary_strategy"], "user_proposed_strategy": "full_system",
            "fixtures": fixtures, "strategies": audits, "paper_only": True, "actual_money_staked_eur": 0,
            "full_ticket_roi_eligible": False,
            "full_ticket_exclusion_reason": observation.get("full_ticket_exclusion_reason", "Probability-only record"),
            "official_roi": None, "positive_expected_roi_demonstrated": False,
            "limitations": ["Frozen predictions and selections stay unchanged", "Live scores are excluded",
                            "Conditional paper loss is not an official settlement or an eligible full-ticket ROI observation",
                            "No model retuning or significance conclusion from a single contest"]}


def render_review(review, probability_evaluation, market_evaluation, output):
    def esc(value):
        return html.escape(str(value))
    fixture_rows = []
    for row in review["fixtures"]:
        state = "Pendiente" if row["covered"] is None else "Cubierto" if row["covered"] else "Fallo"
        date_note = (f"<small>Fecha: {esc(row['forecast_date'])} → {esc(row['actual_date'])}</small>"
                     if row["actual_date"] and row["forecast_date"] != row["actual_date"] else "")
        probabilities = " / ".join(f"{p * 100:.1f}" for p in row["probabilities"])
        result = esc(row["score"] or "Pendiente")
        if row["source_url"]:
            result = f'<a href="{esc(row["source_url"])}">{result}</a>'
        fixture_rows.append(f"<tr><td>{row['position']}</td><td>{esc(row['home_team'])} – {esc(row['away_team'])}{date_note}</td>"
                            f"<td>{esc(''.join(row['selection']))}</td><td>{probabilities}</td><td>{result}</td>"
                            f"<td>{esc(row['actual_sign'] or '—')}</td><td>{state}</td></tr>")
    names = {"full_system": "Sistema completo propuesto", "individual_columns": "Columnas individuales · estrategia principal",
             "robust_full_system": "Sistema robusto", "robust_columns": "Columnas robustas",
             "at_least_10_full_system": "Sistema para alcanzar 10"}
    portfolio_rows = []
    for name, row in review["strategies"].items():
        amount = f"{row['conditional_net_eur']:.2f} €" if row["conditional_net_eur"] is not None else "Pendiente"
        portfolio_rows.append(f"<tr><td>{esc(names.get(name, name))}</td><td>{row['cost_eur']:.2f} €</td>"
                              f"<td>{row['best_hits_lower_bound']}–{row['best_hits_upper_bound']}</td><td>{amount}</td></tr>")
    metrics = []
    for code, row in probability_evaluation["leagues"].items():
        metrics.append(f"<tr><td>{esc(code)}</td><td>{row['matches']}</td><td>{row['candidate']['log_loss']:.4f}</td>"
                       f"<td>{row['comparator']['log_loss']:.4f}</td><td>{100 * row['candidate']['accuracy']:.1f} %</td></tr>")
    league_names = {"es.1": "Primera", "es.2": "Segunda", "es.w.1": "Liga F"}
    market_note = " ".join(
        f"Comparación con cuotas en {market['paired_matches']} partidos de {league_names.get(code, code)}: "
        f"log loss del modelo {market['model']['log_loss']:.4f}; del mercado {market['market']['log_loss']:.4f}. Menor es mejor."
        for code, market in market_evaluation["leagues"].items() if market["paired_matches"]
    ) or "Comparación con mercado pendiente."
    proposal = review["strategies"][review["user_proposed_strategy"]]
    status_note = (f"Hay {review['pending_fixtures']} partido(s) pendiente(s)." if review["pending_fixtures"]
                   else "Todos los partidos tienen un resultado deportivo final.")
    if proposal["sporting_10_plus_impossible"]:
        status_note += " La propuesta ya no puede llegar a 10 aciertos según los resultados deportivos."
    money = f"{proposal['conditional_net_eur']:.2f} €" if proposal["conditional_net_eur"] is not None else "Pendiente"
    probability_file = review.get("probability_evaluation_file", "probability_evaluation_v2.json")
    market_file = review.get("market_evaluation_file", "market_evaluation_v2.json")
    document = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Revisión {esc(review['contest_id'])} · QuantFootball</title><style>
body{{font:16px system-ui;background:#f3f5f8;color:#152538;margin:0}}main{{max-width:1200px;margin:auto;padding:28px}}
h1{{margin:0 0 12px}}h2{{margin-top:32px}}p{{line-height:1.6}}.notice{{background:#fff0d4;border-left:5px solid #a65d00;padding:18px;border-radius:8px}}
.cards{{display:flex;gap:16px;flex-wrap:wrap;margin:22px 0}}.card{{background:white;border-radius:10px;padding:18px;flex:1;min-width:180px}}
.card strong{{display:block;font-size:30px}}.table{{overflow:auto;background:white;border-radius:10px}}table{{border-collapse:collapse;width:100%;font-size:14px}}
th,td{{padding:12px;text-align:left;border-bottom:1px solid #e1e6ed}}th{{background:#e8eef5}}small{{display:block;color:#616d7e;margin-top:5px}}
a{{color:#155dad}}footer{{color:#616d7e;margin:28px 0;font-size:13px}}</style></head><body><main>
<h1>Revisión {esc(review['contest_id'])}</h1><p>Predicción guardada antes del cierre · consulta la fecha de actualización al pie.</p>
<div class="notice">{esc(status_note)} La liquidación oficial permanece pendiente. Motivo de exclusión del ROI completo: {esc(review['full_ticket_exclusion_reason'])}.</div>
<div class="cards"><div class="card">Partidos finalizados<strong>{review['completed_fixtures']} / 14</strong></div>
<div class="card">Máximo posible · propuesta<strong>{proposal['best_hits_upper_bound']} aciertos</strong></div>
<div class="card">Resultado simulado condicionado<strong>{money}</strong>Si los signos oficiales coinciden con los deportivos.</div></div>
<h2>Partido a partido</h2><div class="table"><table><thead><tr><th>Nº</th><th>Partido</th><th>Selección</th><th>Probabilidades 1 / X / 2 (%)</th><th>Marcador</th><th>Signo</th><th>Selección</th></tr></thead><tbody>{''.join(fixture_rows)}</tbody></table></div>
<h2>Todas las estrategias congeladas</h2><p>Los límites contemplan cualquier resultado de los partidos pendientes. No se modifica ninguna columna después de conocer resultados.</p>
<div class="table"><table><thead><tr><th>Estrategia</th><th>Coste simulado</th><th>Mejor columna · límites</th><th>Resultado económico condicionado</th></tr></thead><tbody>{''.join(portfolio_rows)}</tbody></table></div>
<h2>Calidad de las probabilidades</h2><div class="table"><table><thead><tr><th>Competición</th><th>Partidos</th><th>Log loss candidato</th><th>Log loss comparador</th><th>Acierto del favorito</th></tr></thead><tbody>{''.join(metrics)}</tbody></table></div>
<p>{esc(market_note)} La muestra es pequeña y no demuestra una ventaja sostenible.</p>
<h2>Trabajo siguiente</h2><p>Continuar el registro antes del cierre con parámetros fijos. Incorporar porcentajes fiables del público y validar el estimador de premios antes de seleccionar por ROI esperado.</p>
<p><a href="review.json">Datos de esta revisión</a> · <a href="{esc(probability_file)}">Evaluación probabilística</a> · <a href="{esc(market_file)}">Evaluación frente al mercado</a></p>
<footer>Actualizado: {esc(review['created_at'])}. Predicción original: {esc(review['prediction_registered_at'])}. Sin apuestas reales; ROI esperado positivo sin demostrar.</footer>
</main></body></html>"""
    with Path(output).open("x", encoding="utf-8") as handle:
        handle.write(document)


def write_review(record, dataset, probability_evaluation, market_evaluation, output):
    output = Path(output)
    review = review_pair(record, dataset)
    review["probability_evaluation_file"] = "probability_evaluation.json"
    review["market_evaluation_file"] = "market_evaluation.json"
    if output.exists():
        raise ValueError("Choose a new review directory to preserve prior reviews.")
    output.mkdir(parents=True)
    with (output / "review.json").open("x", encoding="utf-8") as handle:
        json.dump(review, handle, ensure_ascii=False, indent=2, allow_nan=False)
    for name, path in (("probability_evaluation.json", probability_evaluation), ("market_evaluation.json", market_evaluation)):
        source = Path(path)
        with (output / name).open("xb") as handle:
            handle.write(source.read_bytes())
    render_review(review, json.loads(Path(probability_evaluation).read_text(encoding="utf-8")),
                  json.loads(Path(market_evaluation).read_text(encoding="utf-8")), output / "dashboard.html")
    return review
