"""Analyze frozen J12 probabilities and portfolios; separate sporting and award evidence."""



import argparse
import hashlib
import html
import json
from datetime import UTC, datetime
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from quantfootball.data.results import ResultLookup
from quantfootball.market.match_study import evaluate_studies
from quantfootball.market.pooling import pool_probabilities
from quantfootball.market.prospective import evaluate_pairs, verify_pair
from quantfootball.quiniela.coverage import (
    best_columns,
    best_full_system,
    threshold_system_frontier,
)
from quantfootball.quiniela.registry import verify_record
from quantfootball.quiniela.review import write_review
from quantfootball.quiniela.risk import portfolio_risk
from quantfootball.quiniela.settlement import settle_columns

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT
raw = ROOT / "data/raw/results_20261014"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output-dir", type=Path, required=True, help="New output directory for reproducing this specific historical analysis")
args = parser.parse_args()
out = args.output_dir
out.mkdir(parents=True, exist_ok=False)
dataset = ROOT / "data/processed/matches_quiniela_20261014.parquet"


def save(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def metrics(p, y):
    return {"matches": len(y), "log_loss": float(-np.log(p[np.arange(len(y)), y]).mean()),
            "brier": float(np.square(p - np.eye(3)[y]).sum(axis=1).mean()),
            "accuracy": float(np.mean(p.argmax(axis=1) == y)),
            "predicted_class_mass": p.mean(axis=0).tolist(),
            "observed_class_frequency": np.bincount(y, minlength=3).astype(float).__truediv__(len(y)).tolist()}


def difference_interval(values):
    rng = np.random.default_rng(20261014)
    samples = rng.choice(values, size=(20000, len(values)), replace=True).mean(axis=1)
    return {"mean": float(np.mean(values)), "descriptive_iid_bootstrap_95": np.quantile(samples, [.025, .975]).tolist(),
            "limitations": "Match-level resampling is descriptive; shared weekly effects and only two observed weekends prevent a robust significance claim."}


seal = verify_record(REAL / "outputs/predictions/registry/2026_j12")
_, values = verify_pair(REAL / "outputs/predictions/probability_pairs/2026_j12")
candidate, comparator, observation, protocol = values
coupon = candidate["coupons"][0]
market = json.loads((REAL / "outputs/predictions/probability_pairs/2026_j12/market.json").read_text(encoding="utf-8"))
consensus = json.loads((raw / "j12_secondary_consensus.json").read_text(encoding="utf-8"))
status_rows = json.loads((raw / "2026-es.1-08.json").read_text(encoding="utf-8"))
lookup = ResultLookup(pd.read_parquet(dataset))
stamp = datetime.fromisoformat(seal["registered_at"])
point = np.array([[f[k] for k in ("p_home", "p_draw", "p_away")] for f in coupon["fixtures"]])
quotes = np.array([f["market_1x2"] for f in market["fixtures"]])
fixtures, indices, targets = [], [], []
for i, (fixture, quote, award) in enumerate(zip(coupon["fixtures"], market["fixtures"], consensus["fixtures"])):
    resolved = lookup.find(fixture, stamp)
    if resolved and (f"{int(resolved['home_goals'])}-{int(resolved['away_goals'])}" != award["score"]
                     or ("1", "X", "2")[resolved["target"]] != award["sign"]):
        raise ValueError("Independent contest summary differs from a final sporting result.")
    if resolved:
        indices.append(i)
        targets.append(resolved["target"])
    outside = [sign for j, sign in enumerate(("1", "X", "2"))
               if not fixture[("p_home", "p_draw", "p_away")[j] + "_low"] <= quotes[i, j]
               <= fixture[("p_home", "p_draw", "p_away")[j] + "_high"]]
    row = {"position": i + 1, "home_team": fixture["home_team"], "away_team": fixture["away_team"],
           "competition_code": fixture["competition_code"], "score_summary": award["score"],
           "awarded_sign_secondary_consensus": award["sign"], "sporting_evaluable": resolved is not None,
           "sporting_exclusion": None if resolved else "Abandoned; 0-0 at interruption is not a completed sporting result",
           "model": point[i].tolist(), "market": quotes[i].tolist(), "favorite": ("1", "X", "2")[point[i].argmax()],
           "model_assigned_actual_probability": float(point[i, resolved["target"]]) if resolved else None,
           "market_assigned_actual_probability": float(quotes[i, resolved["target"]]) if resolved else None,
           "paired_log_loss_difference": float(np.log(quotes[i, resolved["target"]] / point[i, resolved["target"]])) if resolved else None,
           "shared_by_all_primary_columns": len({c["signs"][i] for c in coupon["budgets"]["5.00"]["strategies"]["individual_columns"]["columns"]}) == 1,
           "covered_by_any_primary_column": award["sign"] in {c["signs"][i] for c in coupon["budgets"]["5.00"]["strategies"]["individual_columns"]["columns"]},
           "limited_history": fixture["limited_history"], "home_recent_matches": fixture["recent_home_matches"],
           "away_recent_matches": fixture["recent_away_matches"], "market_outside_base_bootstrap_5_95_for": outside,
           "favorite_stability": fixture["favorite_stability"]}
    fixtures.append(row)
if len(indices) != 13 or not any(m["status"] == "Abandoned" for m in status_rows["matches"]):
    raise ValueError("Expected thirteen final sporting fixtures and one audited abandoned match.")
targets = np.array(targets)
families = {"model": point, "pool_50": pool_probabilities(point, quotes), "market": quotes}
evaluations = {name: metrics(probs[indices], targets) for name, probs in families.items()}
actual = [f["sign"] for f in consensus["fixtures"]]
strategies = {}
for name, strategy in coupon["budgets"]["5.00"]["strategies"].items():
    settlement = settle_columns(strategy["columns"], actual, consensus["prizes"],
                                pleno_prediction=coupon["pleno"]["prediction"], pleno_actual=consensus["pleno"]["sign"])
    strategies[name] = {**settlement, "predicted_risk": strategy["risk"], "selections": strategy.get("selections"),
                        "evidence": consensus["evidence_status"], "official_receipt_written": False}
counterfactual = {}
for name, probabilities in families.items():
    columns = best_columns(probabilities.tolist(), 6)
    system = best_full_system(probabilities.tolist(), 6, min_columns=2)
    threshold11 = max(threshold_system_frontier(probabilities.tolist(), 6, 11), key=lambda p: p["threshold_probability"])
    counterfactual[name] = {}
    for label, plan in (("individual", columns), ("full_system", system), ("threshold_11_full_system", threshold11)):
        risk = portfolio_risk(probabilities.tolist(), plan["columns"])
        counterfactual[name][label] = {
            "columns": plan["columns"], "selections": plan.get("selections"), "risk": risk,
            "settlement_secondary_sources": settle_columns(plan["columns"], actual, consensus["prizes"]),
            "scope": "Retrospective diagnostic only; not a registered strategy or future-performance validation",
        }
probability_evaluation = evaluate_pairs(REAL / "outputs/predictions/probability_pairs", dataset, sporting_snapshots=raw)
market_evaluation = evaluate_studies(REAL / "outputs/predictions/market_matches", dataset, sporting_snapshots=raw)
save(out / "probability_evaluation.json", probability_evaluation)
save(out / "market_evaluation.json", market_evaluation)
write_review(REAL / "outputs/predictions/probability_pairs/2026_j11", dataset,
             out / "probability_evaluation.json", out / "market_evaluation.json", out / "j11_complete")
paired = [r["model"]["log_loss"] - r["market"]["log_loss"] for r in market_evaluation["fixtures"]]
class_diagnostics = {name: evaluations[name]["predicted_class_mass"] for name in evaluations}
money_objective = {
    "ten_hits_unit_payout": consensus["prizes"]["10"]["unit_eur"],
    "eleven_hits_unit_payout": consensus["prizes"]["11"]["unit_eur"],
    "budget_cost": strategies["individual_columns"]["cost_eur"],
    "one_eleven_hit_column_net": float(consensus["prizes"]["11"]["unit_eur"]) - strategies["individual_columns"]["cost_eur"],
    "conclusion": "P(>=10), receiving a cash prize, recovering cost and positive net return are different objectives; realized payouts are unavailable before close.",
}
analysis = {
    "schema_version": 1, "contest_id": "2026_j12", "created_at": datetime.now(UTC).isoformat(),
    "original_seal_sha256": hashlib.sha256((REAL / "outputs/predictions/registry/2026_j12/seal.json").read_bytes()).hexdigest(),
    "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(), "sporting_matches": len(indices),
    "sporting_excluded_matches": 1, "original_strategies": strategies, "fixtures": fixtures,
    "j12_probability_metrics": evaluations,
    "j12_paired_difference": difference_interval([r["paired_log_loss_difference"] for r in fixtures if r["sporting_evaluable"]]),
    "cumulative_market_paired_difference": difference_interval(paired),
    "retrospective_diagnostics": counterfactual, "money_objective": money_objective,
    "class_diagnostics": class_diagnostics, "official_settlement_status": "pending_direct_primary_verification",
    "paper_only": True, "positive_expected_roi_demonstrated": False,
    "limitations": ["Consensus from two independent secondary summaries; no official receipt written",
                    "Abandoned Rayo/Athletic excluded from training and sporting scores, retained for conditional Quiniela accounting",
                    "Only two prospective weekends; bootstrap intervals are descriptive and do not establish a stable advantage",
                    "The 50% mixture and other alternatives were analyzed after outcomes and are not retrospectively registered",
                    "Realized unit prizes cannot be used as pre-close expected prizes",
                    "No closing-market capture, public column shares, lineups, injuries or externally certified timestamps"],
}
save(out / "analysis.json", analysis)

# Export figures for the standalone report; no browser interaction is needed.
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), constrained_layout=True)
labels, colors = ["Modelo", "Mezcla 50%*", "Mercado"], ["#5268a8", "#a1763c", "#177f77"]
for ax, metric, title in zip(axes, ("log_loss", "brier"), ("Log loss · menor es mejor", "Brier · menor es mejor")):
    vals = [evaluations[k][metric] for k in families]
    bars = ax.bar(labels, vals, color=colors)
    ax.bar_label(bars, fmt="%.3f", padding=4)
    ax.set_ylim(0, max(vals) * 1.22)
    ax.set_title(title)
fig.suptitle("J12 · 13 partidos completos; *mezcla evaluada después de resultados")
fig.savefig(out / "probabilities.png", dpi=160)
plt.close(fig)
fig, ax = plt.subplots(figsize=(10, 5), constrained_layout=True)
loss_rows = sorted((r for r in fixtures if r["sporting_evaluable"]), key=lambda r: r["paired_log_loss_difference"])
ax.barh([f"{r['position']}. {r['home_team']}" for r in loss_rows], [r["paired_log_loss_difference"] for r in loss_rows],
        color=["#177f77" if r["paired_log_loss_difference"] < 0 else "#ae5656" for r in loss_rows])
ax.axvline(0, color="#444", lw=1)
ax.set_xlabel("Log loss modelo − mercado · negativo favorece al modelo")
ax.set_title("Dónde gana o pierde calidad la probabilidad asignada al resultado real")
fig.savefig(out / "errors.png", dpi=160)
plt.close(fig)

names = {"full_system": "Doble + triple", "individual_columns": "Seis columnas · principal",
         "robust_full_system": "Sistema robusto", "robust_columns": "Columnas robustas",
         "at_least_10_full_system": "Sistema para ≥10"}
portfolio_rows = "\n".join(f"| {names[k]} | {', '.join(map(str,v['column_hits']))} | {v['max_hits']} | {v['gross_return_eur']:.2f} € | {v['net_eur']:.2f} € |" for k,v in strategies.items())
fixture_rows = "\n".join(
    f"| {r['position']} | {r['home_team']}–{r['away_team']} | {r['score_summary']} ({r['awarded_sign_secondary_consensus']}) | "
    f"{r['model_assigned_actual_probability']*100:.1f}% | {r['market_assigned_actual_probability']*100:.1f}% | "
    f"{'Sí' if r['covered_by_any_primary_column'] else 'No'} |"
    if r["sporting_evaluable"] else f"| {r['position']} | {r['home_team']}–{r['away_team']} | Interrumpido; signo X | Excluido | Excluido | No |"
    for r in fixtures)
metric_rows = "\n".join(f"| {label} | {evaluations[k]['log_loss']:.4f} | {evaluations[k]['brier']:.4f} | {evaluations[k]['accuracy']*100:.1f}% |" for k,label in zip(families,labels))
ci = analysis["cumulative_market_paired_difference"]["descriptive_iid_bootstrap_95"]
limited = [r["position"] for r in fixtures if r["limited_history"]]
outside_count = sum(bool(r["market_outside_base_bootstrap_5_95_for"]) for r in fixtures)
summary = f"""# Análisis de la jornada 12 · 14 de octubre de 2026

## 1. Resultado económico y aciertos

La estrategia principal guardada antes del cierre alcanzó **9 aciertos como máximo**.
Sus seis columnas fueron **8, 8, 9, 7, 9 y 7**. Coste de simulación: **4,50 €**;
retorno **0 €**, neto **−4,50 €**, ROI simulado condicionado **−100 %**.
Dos fuentes independientes coinciden en los quince signos y los seis premios.
La consulta directa al artículo SELAE fue restringida por geografía; se mantiene
pendiente la verificación primaria y no se ha escrito una liquidación oficial.

| Estrategia guardada | Aciertos de cada columna | Máximo | Retorno | Neto |
| --- | --- | ---: | ---: | ---: |
{portfolio_rows}

**El sistema robusto llegó a diez y tampoco cobró**: el premio de diez fue
0 €. Once aciertos pagaron 3,91 €; una sola columna con once habría dejado
un neto de **−0,59 €** sobre los 4,50 €. P(≥10), cobrar y obtener beneficio
no son el mismo objetivo. Estos premios se conocen después de la jornada,
por lo que no sirven como pronóstico de rentabilidad previo al cierre.

Pleno propuesto **M–1**; resultado publicado **1–0**. El modelo asignaba
15,34 % a M–1 y 6,84 % a 1–0. Un único marcador no permite calibrar el Pleno.

## 2. Probabilidades: modelo frente al mercado

Se evalúan **13 partidos completos**. Rayo–Athletic figura como `Abandoned`
en LaLiga: su 0–0 no se añade al entrenamiento ni se puntúa como empate
deportivo. Se mantiene el signo X del resumen de Quiniela para el recuento
económico condicionado. La Liga F no intervino en este boleto.

| Pronóstico | Log loss ↓ | Brier ↓ | Acierto del favorito |
| --- | ---: | ---: | ---: |
{metric_rows}

*La mezcla 50 % es un diagnóstico retrospectivo de entradas que ya existían
antes del cierre; no se presentó ni se registró como apuesta original.*

![Comparación probabilística](probabilities.png)

En los **24 partidos únicos** del estudio de cuotas acumulado, la diferencia
media de log loss modelo−mercado es **{analysis['cumulative_market_paired_difference']['mean']:.4f}**.
Positivo indica peor resultado del modelo. El intervalo descriptivo de bootstrap
por partido es **[{ci[0]:.4f}, {ci[1]:.4f}]**. Solo hay dos fines de semana:
no es una prueba sólida de ventaja ni de inferioridad estable. El mercado
ha funcionado mejor en log loss y Brier en la muestra observada; eso justifica
evaluarlo como parte de un candidato, no afirmar un ROI positivo.

![Diferencias por partido](errors.png)

## 3. Partido a partido

Las probabilidades son las asignadas al resultado finalmente observado, no
probabilidades recalculadas después. Rayo se excluye del análisis deportivo.

| Nº | Partido | Resultado | P real · modelo | P real · mercado | Cubierto por alguna columna principal |
| --- | --- | --- | ---: | ---: | --- |
{fixture_rows}

Los mayores costes de log loss frente al mercado están en Racing–Valencia,
Burgos–Granada y Mallorca–Las Palmas. En Racing la X recibió **20,62 %**
del modelo y **26,80 %** del mercado. Burgos–Granada terminó en 2: el modelo
le asignaba **24,61 %**, frente a **30,65 %**. En Mallorca la victoria local
tenía **48,93 %**, frente a **58,94 %**. También hay encuentros donde el
modelo fue mejor: Andorra, Eldense, Betis y Almería. La discrepancia debe
medirse con probabilidades completas, no solo con el favorito acertado.

## 4. Dobles, triples y concentración de las columnas

Las seis columnas principales compartían **11 signos de 14**. Solo variaban
Elche–Celta, Andorra–Castellón y Oviedo–Eibar. Cuatro signos compartidos
fallaron: Rayo, Racing, Levante y Burgos. Además, ninguna columna llevaba
la X de Elche. Por eso el máximo quedó en nueve.

La concentración es consecuencia de maximizar P(14) con seis columnas;
no es por sí sola un error del optimizador. El cálculo ya considera la
dependencia entre columnas por compartir resultados. La P(≥10) prevista
era **18,55 %**: una jornada sin diez tenía **81,45 %** de probabilidad
bajo el propio modelo. El resultado económico desfavorable no demuestra
por sí solo que el algoritmo de asignación falle.

La alternativa robusta puso triple en Elche y doble en Andorra; alcanzó
diez. No debe pasar a estrategia principal solo por ganar esta comparación
de una jornada. En `analysis.json` quedan comparados también boletos de mercado,
mezcla fija y sistemas para ≥11, todos marcados como retrospectivos.

## 5. Limitaciones concretas detectadas

1. **El mercado solo se mostraba como comparación**; sus probabilidades no
   influían en la propuesta. Es la primera variable externa que ya tenemos
   con fecha y procedencia anteriores a los partidos.
2. **Pronóstico temprano**: el corte fue 05-10, con datos hasta el 04-10,
   y las cuotas del 05-10. Hasta el cierre del 10-10 transcurrieron casi
   cinco días. Córdoba jugó el 05-10 y ese resultado no estaba en el modelo
   al preparar J12. No hay cuotas de cierre guardadas y no se pueden inventar.
3. **Ascensos e historial corto**: las posiciones {', '.join(map(str,limited))}
   tienen al menos un equipo con menos de diez partidos recientes en esa
   división. Deportivo, Racing, Eldense, Mallorca y Oviedo necesitan una
   evaluación específica de transferencia de fuerza y reducción de confianza.
   El modelo de goles principal se ajusta por división; las variables de forma
   transfieren parte de la historia, pero la mezcla sigue dando gran peso
   al componente de goles con poca información de la nueva división.
4. **Incertidumbre parcial**: el consenso de mercado sale de alguna banda
   5–95 % del bootstrap del modelo en **{outside_count} partidos**. El mercado
   no es la verdad, pero las bandas no representan toda la incertidumbre:
   omiten disponibilidad de jugadores, estructura del modelo y error de cuotas.
5. **Objetivo económico incompleto**: faltan porcentajes del público y su
   dependencia entre signos, recaudación/bote antes del cierre y un modelo
   validado de premios. Las cuotas de casas de apuestas no sustituyen a los
   porcentajes jugados en La Quiniela.
6. **Evaluación administrativa**: los evaluadores antiguos dejaban Rayo como
   pendiente. Ahora lo registran como exclusión deportiva con fuente y hash;
   sigue contando en el recuento de Quiniela si se confirma su signo oficial.

## 6. Cambios y experimentos, por orden

### Prioridad 1: candidato que incorpore cuotas

Preparar una mezcla fija **50 % modelo + 50 % mercado**, comparada con el
modelo congelado y mercado puro. El peso es una elección inicial conservadora,
no el mejor peso seleccionado con estos resultados. No ajustar temperatura,
sesgos o peso con esta pequeña muestra. Nuevo protocolo y cohorte futura;
registrar cada versión antes del cierre y no sustituir registros anteriores.
Liga F conserva el modelo propio mientras falten cuotas válidas.

### Prioridad 2: mejorar el momento y la calidad de los datos

Generar la decisión final cerca del cierre, conservando el margen para validar
el boleto y antes de todos sus inicios. Incorporar únicamente resultados
finalizados conocidos antes del corte. Capturar cuotas de decisión y una
segunda captura cercana al cierre para analizar cambios de mercado. Guardar
para cada variable fecha del hecho y fecha de disponibilidad.

### Prioridad 3: objetivos de cartera más útiles

Comparar P(14), P(≥11), probabilidad de cobrar, recuperar el coste y beneficio
esperado. P(≥11) sigue siendo un indicador de aciertos, no de rentabilidad.
Cuando existan datos del público, valorar cada columna por el premio esperado
por categoría y su popularidad; hasta entonces mantener cobertura como objetivo
explícito y la simulación económica como evaluación posterior.

### Prioridad 4: transferencia y calendario

Evaluar en temporadas históricas separadas un modelo jerárquico de fuerza
entre Primera/Segunda para ascensos, con priors de goles ajustados por categoría.
Añadir calendario completo de clubes (Liga, Copa y competición europea) para
descanso real y carga reciente. Los descansos actuales solo ven las ligas del
dataset. Añadir bajas y alineaciones únicamente con fuente autorizada y hora
de publicación; no reconstruir lesiones conocidas después como si fueran previas.

### Prioridad 5: calibración y nuevos modelos

Con suficientes predicciones nuevas, estudiar calibración por competición y
resultado en ventanas temporales, con regularización. Probar corrección residual
del mercado con un modelo sencillo antes de añadir otra red neuronal. Goles,
forma y Elo ya están incorporados; añadir columnas duplicadas o complejidad
sin una comparación temporal independiente no demuestra mejora.

## 7. Trabajo ejecutado y pendiente

- Nuevo histórico: **10.993 resultados**, +21 (9 Primera y 12 Segunda).
  Rayo interrumpido queda fuera; Liga F sigue hasta el 04-10 y su siguiente
  jornada capturada aún no había comenzado.
- Evaluación de 27 partidos de boletos: 14 de J11 y 13 de J12, con una exclusión
  deportiva auditada y sin pendientes deportivos sin clasificar.
- Evaluación de cuotas en 24 partidos únicos; se conserva la primera predicción
  y no se duplica un encuentro por aparecer en dos capturas.
- Revisión final deportiva de J11: disponible en `j11_complete/dashboard.html`.
  Su Pleno de selecciones sigue fuera de la cohorte económica.
- Predicciones, configuraciones de modelos y sellos anteriores preservados.
- Liquidación primaria de J12 pendiente de acceso o extracto oficial; todas
  las cifras de retorno aquí están expresamente marcadas como simulación
  condicionada a las dos fuentes independientes concordantes.

No hay evidencia de ROI esperado positivo. El cambio con más fundamento ahora
es incorporar el mercado y reducir la antigüedad de los datos; las mejoras deben
ganarse su lugar en jornadas nuevas, no escogerse por cómo habrían acertado esta.

## Fuentes y reproducibilidad

- [LaLiga Primera, jornada 8](https://www.laliga.com/laliga-easports/resultados/2026-27/jornada-8)
- [LaLiga Segunda, jornada 9](https://www.laliga.com/laliga-hypermotion/resultados/2026-27/jornada-9)
- [Resumen independiente de J12](https://www.quinielafutbol.info/resultados/jornada-quiniela-domingo-11-de-octubre-de-2026.html)
- [Segunda comprobación del escrutinio](https://comprobarloteria.com/quiniela/2026-10-11/)
- [Documentación de calibración de scikit-learn](https://scikit-learn.org/stable/modules/calibration.html)

`analysis.json` guarda probabilidades, aciertos, métricas, límites, procedencia
y comparaciones retrospectivas. `probability_evaluation.json` y
`market_evaluation.json` incluyen todas las observaciones elegibles. Los datos
capturados y sus hashes se conservan en `data/raw/results_20261014`.
"""
with (out / "REPORT.md").open("x", encoding="utf-8") as handle:
    handle.write(summary)
fixture_html = "".join(f"<tr><td>{r['position']}</td><td>{html.escape(r['home_team'])}–{html.escape(r['away_team'])}</td>"
                        f"<td>{r['score_summary']} · {r['awarded_sign_secondary_consensus']}</td><td>{'Sí' if r['covered_by_any_primary_column'] else 'No'}</td></tr>" for r in fixtures)
portfolio_html = "".join(f"<tr><td>{names[k]}</td><td>{', '.join(map(str,v['column_hits']))}</td><td>{v['max_hits']}</td><td>{v['net_eur']:.2f} €</td></tr>" for k,v in strategies.items())
document = f"""<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Revisión J12 · QuantFootball</title>
<style>body{{font:16px system-ui;background:#f3f5f8;color:#193044;margin:0}}main{{max-width:1080px;margin:auto;padding:24px}}p{{line-height:1.6}}.notice{{padding:18px;background:#fff0d8;border-left:4px solid #aa6923}}.cards{{display:flex;gap:16px;flex-wrap:wrap;margin:20px 0}}.card{{background:white;padding:20px;flex:1;border-radius:12px}}strong.metric{{display:block;font-size:32px}}table{{width:100%;border-collapse:collapse;background:white}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #ddd}}.scroll{{overflow:auto}}img{{width:100%;height:auto}}a{{color:#185d96}}details{{background:white;padding:16px;margin:16px 0}}pre{{white-space:pre-wrap;line-height:1.6;font:14px system-ui}}h2{{margin-top:30px}}</style><main>
<h1>Jornada 12 · revisión exhaustiva</h1><p>14 de octubre de 2026 · predicciones originales conservadas</p>
<div class="notice">Resultados y premios concordantes en dos fuentes independientes. Verificación directa SELAE pendiente por restricción geográfica. Rayo–Athletic interrumpido: excluido de las métricas deportivas, retenido para el recuento condicionado de Quiniela.</div>
<div class="cards"><div class="card">Principal · mejor columna<strong class="metric">9 aciertos</strong></div><div class="card">Neto simulado condicionado<strong class="metric">−4,50 €</strong></div><div class="card">Partidos deportivos<strong class="metric">13 / 14</strong></div></div>
<h2>Todas las estrategias guardadas</h2><div class="scroll"><table><tr><th>Estrategia</th><th>Aciertos de columnas</th><th>Máximo</th><th>Neto</th></tr>{portfolio_html}</table></div>
<p>El sistema robusto alcanzó diez pero diez no cobró. Once pagó 3,91 €: una columna con once tampoco recuperaría el coste total de 4,50 €.</p>
<h2>Probabilidades y errores</h2><img src="probabilities.png" alt="Comparación de log loss y Brier"><img src="errors.png" alt="Diferencias de log loss por partido">
<p>La mezcla se analizó después de los resultados; es un candidato para investigar en jornadas futuras. Solo hay dos fines de semana de evaluación prospectiva.</p>
<h2>Partido a partido</h2><div class="scroll"><table><tr><th>Nº</th><th>Partido</th><th>Resultado publicado</th><th>Alguna columna principal lo cubre</th></tr>{fixture_html}</table></div>
<h2>Prioridades</h2><ol><li>Evaluar mezcla fija de modelo y cuotas frente al mercado puro.</li><li>Preparar la decisión cerca del cierre con datos disponibles y guardar cambios de cuotas.</li><li>Comparar aciertos, cobro, recuperación del gasto y beneficio por separado.</li><li>Evaluar transferencia de fuerza para ascensos y calendario completo.</li><li>Calibrar con suficientes observaciones nuevas; mantener cada versión en su cohorte.</li></ol>
<details><summary>Leer el análisis completo</summary><pre>{html.escape(summary)}</pre></details>
<p><a href="REPORT.md">Informe completo</a> · <a href="analysis.json">Todos los cálculos</a> · <a href="j11_complete/dashboard.html">J11 final</a></p>
<p>Registro simulado; no acredita una apuesta real. Rentabilidad positiva sin demostrar.</p></main></html>"""
with (out / "dashboard.html").open("x", encoding="utf-8") as handle:
    handle.write(document)
print(json.dumps({"j12_metrics": evaluations, "cumulative_difference": analysis["cumulative_market_paired_difference"],
                  "primary_hits": strategies["individual_columns"]["column_hits"], "robust_best_hits": strategies["robust_full_system"]["max_hits"],
                  "outside_bootstrap_band_matches": outside_count, "output": str(out)},ensure_ascii=False,indent=2))
