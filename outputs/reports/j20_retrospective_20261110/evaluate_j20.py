"""Score saved J20 research predictions against separate sporting and SELAE results."""

import html
import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

import numpy as np
import pandas as pd

from quantfootball.data.results import ResultLookup
from quantfootball.market.prospective import scores
from quantfootball.quiniela.registry import digest, write_new
from quantfootball.quiniela.settlement import settle_columns

STAGE = Path(__file__).resolve().parent
ROOT = Path.cwd()
ACTUAL_SIGNS = "2X221X1222XX21"
ACTUAL_PLENO = "1-2"
PRIZES = {
    "10": {"winners": 89116, "unit_eur": "3.41"},
    "11": {"winners": 17496, "unit_eur": "14.48"},
    "12": {"winners": 2301, "unit_eur": "110.13"},
    "13": {"winners": 185, "unit_eur": "1369.75"},
    "14": {"winners": 6, "unit_eur": "90099.00"},
    "15": {"winners": 1, "unit_eur": "1647986.55"},
}
LABELS = {
    "individual_columns": "Columnas individuales · principal",
    "full_system": "Sistema completo",
    "robust_full_system": "Sistema completo robusto",
    "robust_columns": "Columnas robustas",
    "at_least_10_full_system": "Sistema orientado a 10+",
}
LEAGUES = {"es.1": "Primera", "es.2": "Segunda", "es.w.1": "Liga F"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def table(headers, rows):
    head = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(x))}</td>" for x in row) + "</tr>"
        for row in rows
    )
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def decimal(value, places=2):
    return f"{value:.{places}f}".replace(".", ",")


def main():
    design = read(STAGE / "design.json")
    forecast_path = STAGE / "forecast/forecast.json"
    forecast = read(forecast_path)
    coupon = forecast["coupons"][0]
    training = STAGE / "matches_j20_before_20261107.parquet"
    assert not forecast["prospective"] and forecast["registration_status"] == "unregistered"
    assert digest(training) == design["dataset_sha256"] == forecast["input_preflight"]["dataset_sha256"]
    assert forecast["input_preflight"]["rows"] == design["training_rows"]
    assert forecast["input_preflight"]["training_rows_before_cutoff"] == design["training_rows"]
    assert forecast["input_preflight"]["config_sha256"] == design["config_sha256"]
    assert coupon["model"]["bootstrap_draws"] == design["bootstrap_draws"]
    assert coupon["cutoff"] == "2026-11-07" and coupon["model"]["training_last_date"] < coupon["cutoff"]

    # This snapshot is read only after the forecast is written, to evaluate realized outcomes.
    observed_path = ROOT / "data/processed/matches_quiniela_20261110.parquet"
    observed = ResultLookup(pd.read_parquet(observed_path))
    matches = []
    score_rows = []
    for position, fixture in enumerate(coupon["fixtures"], 1):
        assert fixture["position"] == position
        p = np.array([fixture[k] for k in ("p_home", "p_draw", "p_away")])
        assert np.isfinite(p).all() and (p > 0).all() and np.isclose(p.sum(), 1)
        official = ACTUAL_SIGNS[position - 1]
        row = {
            "position": position, "competition_code": fixture["competition_code"],
            "home_team": fixture["home_team"], "away_team": fixture["away_team"],
            "probabilities_1x2": p.tolist(), "favorite": "1X2"[int(p.argmax())],
            "official_sign": official, "sporting_score": None, "sporting_metrics": None,
            "settlement_basis": "official_draw" if position == 14 else "sporting_result",
        }
        result = observed.find(fixture)
        if position == 14:
            assert result is None
        else:
            assert result is not None and "1X2"[result["target"]] == official
            row["sporting_score"] = f'{result["home_goals"]}-{result["away_goals"]}'
            row["sporting_metrics"] = scores(p, result["target"])
            score_rows.append(row)
        matches.append(row)
    pleno_result = observed.find(coupon["pleno"])
    assert f'{pleno_result["home_goals"]}-{pleno_result["away_goals"]}' == ACTUAL_PLENO
    assert len(score_rows) == 13
    evaluation = {}
    for label in ("all", *LEAGUES):
        group = [r for r in score_rows if label == "all" or r["competition_code"] == label]
        evaluation[label] = {
            "matches": len(group),
            "favorite_hits": sum(r["favorite"] == r["official_sign"] for r in group),
            **{metric: mean(r["sporting_metrics"][metric] for r in group)
               for metric in ("log_loss", "brier")},
        }
    plans = coupon["budgets"]["5.00"]["strategies"]
    settlements = {
        name: settle_columns(plan["columns"], ACTUAL_SIGNS, PRIZES,
                             pleno_prediction=coupon["pleno"]["prediction"], pleno_actual=ACTUAL_PLENO)
        for name, plan in plans.items()
    }
    primary = settlements[design["primary_strategy"]]
    assert len(primary["column_hits"]) == 6 and primary["cost_eur"] == 4.5
    assert all(len({tuple(c["signs"]) for c in plan["columns"]}) == len(plan["columns"])
               for plan in plans.values())
    report = {
        "evaluated_at": datetime.now(UTC).isoformat(), "design": design,
        "forecast_sha256": digest(forecast_path), "sporting_evaluation_dataset_sha256": digest(observed_path),
        "official_signs": ACTUAL_SIGNS, "official_pleno": ACTUAL_PLENO, "unit_prizes": PRIZES,
        "pleno_prediction": coupon["pleno"]["prediction"], "matches": matches,
        "sporting_evaluation": evaluation, "settlements": settlements,
        "primary_settlement": primary, "expected_roi": None,
    }
    write_new(STAGE / "report.json", report)

    selected_columns = plans[design["primary_strategy"]]["columns"]
    coverage_table = table(
        ["Cartera", "Aciertos por columna", "Mejor", "Coste", "Cobro", "Saldo"],
        [[LABELS[name], ", ".join(map(str, s["column_hits"])), s["max_hits"],
          decimal(s["cost_eur"]) + " €", decimal(s["gross_return_eur"]) + " €",
          decimal(s["net_eur"]) + " €"]
         for name in (design["primary_strategy"], *[n for n in plans if n != design["primary_strategy"]])
         for s in [settlements[name]]],
    )
    probability_table = table(
        ["N.º", "Partido", "P(1)", "P(X)", "P(2)", "Oficial", *[f"C{i}" for i in range(1, 7)]],
        [[r["position"], r["home_team"] + " – " + r["away_team"],
          *[decimal(p * 100, 1) + " %" for p in r["probabilities_1x2"]],
          r["official_sign"] + (" (sorteo)" if r["position"] == 14 else ""),
          *[col["signs"][r["position"] - 1] for col in selected_columns]] for r in matches],
    )
    metrics_table = table(
        ["Liga", "Partidos", "Favoritos acertados", "Log loss", "Brier"],
        [[LEAGUES.get(code, "Total"), r["matches"], r["favorite_hits"],
          decimal(r["log_loss"], 4), decimal(r["brier"], 4)] for code, r in evaluation.items()],
    )
    adjudication = design["sporting_metrics_exclusions"][0]["source_url"]
    page = f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>J20 · reconstrucción retrospectiva</title>
<style>body{{font:16px/1.55 system-ui;background:#f3f6fa;color:#163047;max-width:1140px;margin:36px auto;padding:0 20px}}section{{background:#fff;border:1px solid #dce3e9;border-radius:12px;padding:20px;margin:18px 0}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{text-align:left;padding:9px;border-bottom:1px solid #dce3e9}}.scroll{{overflow:auto}}.note{{background:#fff2d5;padding:14px}}a{{color:#096aab}}</style>
<h1>J20 · reconstrucción retrospectiva</h1><p class="note">Modelo base de la J18 entrenado con corte exclusivo del 7 de noviembre de 2026 a las 00:00 de Madrid. Ejecución posterior al escrutinio. Los resultados previos se reconstruyeron a partir de capturas archivadas el 10 de noviembre.</p>
<section><h2>Liquidación simulada</h2><p>La cartera principal usa seis columnas y cuesta 4,50 €. El Pleno estimado es {html.escape(report['pleno_prediction'])} y el observado es {ACTUAL_PLENO}. <a href="{html.escape(design['source_coupon_order'])}">Escrutinio de SELAE</a></p>{coverage_table}</section>
<section><h2>Probabilidades y columnas</h2>{probability_table}<p>En la casilla 14 se muestra el pronóstico deportivo hipotético del modelo. El signo sorteado cuenta para el cobro y la casilla se excluye de las métricas deportivas. <a href="{html.escape(adjudication)}">Aviso de SELAE</a></p></section>
<section><h2>Evaluación deportiva</h2>{metrics_table}<p>El entrenamiento contiene 11.082 partidos. Los quince cruces del boleto quedan fuera. La última fecha deportiva del histórico es el 6 de noviembre para Primera y el 2 para Segunda y Liga F.</p><p>El cálculo usa el modelo base porque el proyecto carece de cuotas archivadas de la J20 anteriores al cierre. La evaluación se guarda en el archivo de investigación retrospectiva.</p><p><a href="report.json">Resultados en JSON</a> · <a href="forecast/dashboard.html">Panel de estrategias del modelo</a></p></section></html>'''
    with (STAGE / "dashboard.html").open("x", encoding="utf-8") as handle:
        handle.write(page)
    print(json.dumps({"primary": primary, "sporting": evaluation, "pleno": report["pleno_prediction"],
                      "secondary": {k: [v["max_hits"], v["gross_return_eur"]]
                                    for k, v in settlements.items() if k != design["primary_strategy"]}},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
