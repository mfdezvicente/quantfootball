"""Freeze paired paper coverage portfolios after a verified prospective cycle."""

import argparse
import html
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from quantfootball.data.active import resolve_active
from quantfootball.market.prospective import evaluate_pairs, verify_pair
from quantfootball.quiniela.decision import verify_decision
from quantfootball.quiniela.registry import (
    digest,
    register_forecast,
    registry_summary,
    validate_registration,
    verify_record,
    write_new,
)

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cycle-dir", "observation", "pair-root", "decision-root", "coverage-root", "output-dir"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--contest-date", required=True, help="Verified nominal contest date, YYYY-MM-DD")
    args = parser.parse_args()
    if datetime.fromisoformat(args.contest_date).date().isoformat() != args.contest_date:
        parser.error("Use a nominal calendar contest date, not a timestamp.")
    if args.output_dir.exists():
        parser.error("Use a new output directory; reports and registrations are immutable.")
    observation = read(args.observation)
    contest = observation["contest_id"]
    status = read(args.cycle_dir / "run_status.json")
    if status.get("status") != "completed" or not status.get("registered_pair"):
        parser.error("The original probability cycle must complete before coverage registration.")
    pair_folder = args.pair_root / contest
    pair_seal, values = verify_pair(pair_folder)
    if values[2] != observation:
        parser.error("The confirmed observation differs from the frozen probability pair.")
    candidate, comparator, _, protocol = values
    decision_folder = args.decision_root / contest
    decision = verify_decision(decision_folder)
    if read(decision_folder / "observation.json") != observation:
        parser.error("Economic decision and probability pair refer to different observations.")
    if decision["action"] != "abstain" or decision["stake_eur"] != 0:
        parser.error("This workflow only records paper alternatives alongside economic abstention.")
    if protocol["primary_strategy"] != "individual_columns" or protocol["maximum_budget_eur"] != 5:
        parser.error("This coverage extension expects the frozen 5 EUR P(14) protocol.")
    active = resolve_active(ROOT)
    evaluation = evaluate_pairs(args.pair_root, active["dataset"])
    evaluated = [row for row in evaluation["records"] if row["record"] == contest]
    if len(evaluated) != 1 or evaluated[0]["status"] == "invalid":
        parser.error("The probability pair or its market attachment failed verification.")
    arms = {}
    for name, report, folder in (("candidate", candidate, "pool50"), ("comparator", comparator, "base")):
        original = args.cycle_dir / folder / "forecast.json"
        if read(original) != report:
            parser.error("The cycle forecast differs from its registered probability arm.")
        manifest = {
            **observation,
            "schema_version": 2,
            "maximum_budget_eur": protocol["maximum_budget_eur"],
            "contest_date": args.contest_date,
            "primary_strategy": protocol["primary_strategy"],
            "cohort": "pool50_20261014_coverage",
            "arm": name,
            "protocol_sha256": digest(pair_folder / "protocol.json"),
            "probability_pair_seal_sha256": digest(pair_folder / "seal.json"),
            "interpretation": "One paper alternative per arm, not a combined purchase or an economic investment decision",
        }
        target = args.coverage_root / name / contest
        if target.exists():
            seal = verify_record(target)
            if (seal["original_forecast_sha256"] != digest(original)
                    or read(target / "manifest.json") != manifest):
                parser.error("Existing coverage record has different immutable inputs.")
        else:
            # A separate pre-registration input avoids changing the pair or its original reports.
            manifest_path = args.cycle_dir / (name + "_coverage_manifest.json")
            if manifest_path.exists():
                if read(manifest_path) != manifest:
                    parser.error("Existing coverage manifest differs from the frozen protocol.")
            else:
                write_new(manifest_path, manifest)
            seal = register_forecast(original, manifest_path, args.coverage_root / name)
        validate_registration(read(target / "forecast.json"), read(target / "manifest.json"),
                              datetime.fromisoformat(seal["registered_at"]))
        coupon = report["coupons"][0]
        strategy = next(iter(coupon["budgets"].values()))["strategies"][protocol["primary_strategy"]]
        arms[name] = {
            "registered_at": seal["registered_at"],
            "record_path": str(target.resolve()),
            "seal_sha256": digest(target / "seal.json"),
            "column_count": strategy["column_count"],
            "theoretical_cost_eur": strategy["cost_eur"],
            "coverage_p14": strategy["coverage"],
            "pleno_prediction": coupon["pleno"]["prediction"],
            "registry_summary": registry_summary(args.coverage_root / name),
        }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    image_info = observation.get("order_verification", {})
    image_file = ROOT / image_info["image_path"]
    if digest(image_file) != image_info["image_sha256"]:
        raise ValueError("The user-provided coupon image differs from the confirmed observation.")
    shutil.copyfile(image_file, args.output_dir / "official_coupon_user.png")
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "contest_id": contest,
        "paper_only": True,
        "probability_pair": pair_seal,
        "market_attachment_verified": (pair_folder / "market_seal.json").exists(),
        "closes_at": observation["closes_at"],
        "order_verification": image_info,
        "official_inputs_independently_verified": False,
        "coverage_alternatives": arms,
        "economic_decision": decision,
        "economic_seal_sha256": digest(decision_folder / "seal.json"),
        "actual_purchase_verified": False,
        "real_money_stake_eur": 0,
        "positive_expected_roi_demonstrated": False,
        "probability_evaluation": evaluation,
        "limitations": [
            "User image confirms ordered teams; URL and contest/date are not visible in the crop",
            "Contest attribution uses conversation context and audited league fixtures",
            "Each arm is a separate hypothetical alternative; their costs are not a combined stake",
            "Probability pair, coverage cash ledgers and economic abstention are separate records",
            "The economic decision preceded inference, so its missing_probability_forecast reason describes that moment",
            "No data source establishes positive expected ROI; no purchase is performed",
            "Fixtures shared with other probability studies are not independent extra observations",
        ],
    }
    write_new(args.output_dir / "report.json", report)
    write_new(args.output_dir / "probability_evaluation.json", evaluation)
    pack = next(iter(candidate["coupons"][0]["budgets"].values()))
    plan = pack["strategies"][protocol["primary_strategy"]]
    label = contest.split("_")[-1].upper()
    theoretical_cost = f'{arms["candidate"]["theoretical_cost_eur"]:.2f}'.replace(".", ",")
    rows, selection = [], [label + " · SIMULACIÓN 50/50 · sin compra",
                          f'{plan["column_count"]} columnas independientes: {theoretical_cost} € teóricos', ""]
    for i, fixture in enumerate(candidate["coupons"][0]["fixtures"]):
        signs = [c["signs"][i] for c in plan["columns"]]
        title = fixture["home_team"] + " — " + fixture["away_team"]
        rows.append("<tr><td>" + str(i+1) + "</td><td>" + html.escape(title) + "</td>"
                    + "".join("<td>" + html.escape(s) + "</td>" for s in signs) + "</tr>")
        selection.append(f"{i+1:2}. {title}: " + " | ".join(signs))
    selection.extend(["", "Pleno: " + arms["candidate"]["pleno_prediction"],
                      "Decisión económica: no apostar; gasto real 0 €."])
    (args.output_dir / "selection.txt").write_text("\n".join(selection), encoding="utf-8")
    coverage = arms["candidate"]["coverage_p14"]
    stamp = datetime.fromisoformat(pair_seal["registered_at"]).astimezone(ZoneInfo("Europe/Madrid"))
    close = datetime.fromisoformat(observation["closes_at"]).astimezone(ZoneInfo("Europe/Madrid"))
    page = f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(label)} · simulación registrada</title>
<style>body{{font:16px/1.55 system-ui;background:#f3f6fa;color:#163047;max-width:1120px;margin:38px auto;padding:0 22px}}section{{background:white;border:1px solid #dce3e9;border-radius:12px;padding:20px;margin:20px 0}}.notice{{background:#e5f2e9;padding:16px;border-left:4px solid #27814b}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:9px;border-bottom:1px solid #e1e6eb;text-align:left}}.scroll{{overflow:auto}}a{{color:#096aab}}img{{max-width:350px;width:100%;height:auto}}.muted{{color:#536b7d}}</style>
<h1>{html.escape(label)} · pareja 50/50 registrada</h1><p class="notice">Registrada el {stamp:%d/%m/%Y a las %H:%M}, hora de Madrid, antes del cierre del {close:%d/%m/%Y a las %H:%M}.</p>
<section><h2>Qué queda registrado</h2><p>Los catorce partidos tienen pronóstico del modelo y de la mezcla fija. Los masculinos incorporan cuotas reales; las posiciones femeninas conservan el modelo propio. Las columnas, configuración y entradas quedan congeladas.</p><p>La estrategia principal son {plan['column_count']} columnas independientes por <b>{theoretical_cost} € teóricos por alternativa</b>, dentro del límite de 5 € del experimento. El comparador y la mezcla son dos alternativas; no se suman como una compra.</p><p><b>Decisión económica: no apostar. Gasto real: 0 €.</b> La estimación de rentabilidad sigue sin evidencia suficiente.</p></section>
<section><h2>Columnas de la mezcla 50/50 · simulación</h2><div class="scroll"><table><tr><th>Nº</th><th>Partido</th>'''+''.join(f'<th>C{i+1}</th>' for i in range(plan['column_count']))+'''</tr>'''+''.join(rows)+f'''</table></div><p>Pleno: <b>{html.escape(arms['candidate']['pleno_prediction'])}</b>. Cobertura estimada P(14): {coverage:.4%}, condicionada al modelo y sus supuestos; no es probabilidad de beneficio.</p><p><a href="selection.txt">Texto de la selección</a> · <a href="../../predictions/coverage_pool50/candidate/{contest}/dashboard.html">Explorar mezcla</a> · <a href="../../predictions/coverage_pool50/comparator/{contest}/dashboard.html">Explorar comparador</a></p></section>
<section><h2>Confirmación del boleto</h2><img src="official_coupon_user.png" alt="Captura aportada por el usuario con las quince posiciones del boleto"><p class="muted">Confirmación manual mediante la captura del usuario. El recorte muestra orden, equipos y géneros; no muestra URL, fecha ni número de jornada. La atribución al concurso se apoya en la conversación y en los cruces contrastados con LaLiga.</p></section>
<section><h2>Cómo se evaluará</h2><p>Resultados deportivos para log loss, Brier y calibración; signos adjudicados y premios oficiales para liquidar las carteras de cobertura en papel. Los premios desconocidos permanecen pendientes y las decisiones económicas mantienen su propio registro. No se escogerá después la estrategia que mejor haya salido.</p><p>La pareja tiene {evaluation['pending_unique_fixtures']} partidos pendientes. El protocolo conserva el final del 1 de julio de 2027. Los modelos no se ajustan con esta jornada.</p><p>El registro económico se hizo antes del cálculo y conserva el motivo de falta de pronóstico en ese momento, además de los bloqueos económicos. Los pronósticos ahora disponibles se guardan en sus registros propios.</p></section></html>'''
    (args.output_dir / "dashboard.html").write_text(page, encoding="utf-8")
    print(json.dumps({"contest_id":contest,"probability_pair_registered":True,
                      "coverage_arms":arms,"economic_action":decision["action"],
                      "real_money_stake_eur":0,"report":str(args.output_dir)},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
