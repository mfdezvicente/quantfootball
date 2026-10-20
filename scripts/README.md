# Comandos del proyecto

Ejecutar desde la raíz, después de instalar `python -m pip install -e ".[dev]"`.
Cada comando tiene `--help`. Usar una carpeta de salida nueva para cada experimento;
no sobrescribir pronósticos o protocolos registrados.

| Tarea | Comandos |
|---|---|
| Comprobar snapshot y configuración activos | `check_active_inputs.py` |
| Recuperar resultados históricos fijados de OpenFootball | `fetch_spanish_snapshot.py` |
| Construir datos masculinos / Liga F | `build_spanish_dataset.py`, `build_ligaf_dataset.py` |
| Capturar resultados actuales / actualizar dataset | `capture_current_results.py`, `update_current_dataset.py` |
| Configurar cuotas localmente | `configure_odds_api.ps1` |
| Consultar o capturar cuotas | `fetch_market_odds.py` |
| Planificar una jornada | `plan_spain.py`, `plan_quiniela.py` |
| Comparar modelo y mercado | `compare_market.py`, `forecast_market.py` |
| Preparar el candidato 50/50 | `plan_market_pool.py` |
| Ejecutar un ciclo prospectivo | `run_prospective_cycle.py` |
| Registrar / evaluar decisiones y pronósticos | `forecast_registry.py`, `probability_registry.py`, `economic_registry.py` |
| Evaluar variables controladas | `evaluate_ablation_research.py` |
| Evaluar familias de goles y calibración | `evaluate_goal_flex_research.py` |
| Evaluar redes / dinámica / transferencia | `evaluate_neural.py`, `evaluate_dynamic.py`, `evaluate_transfer.py` |
| Auditar premios / fuentes | `audit_prize_economics.py`, `audit_official_archive.py` |
| Investigar carteras y riesgo | `optimize_economic_research.py`, `analyze_portfolio_risk.py`, `analyze_allocations.py` |
| Generar paneles | `render_dashboard.py` |

Las capturas de cuotas pueden consumir créditos de la cuenta del usuario. El ciclo
prospectivo requiere orden y cierre del boleto verificados y datos anteriores al
cierre. No es un programador automático.

Los comandos históricos restantes conservan sus nombres y parámetros para reproducir
las investigaciones anteriores. Consulte los documentos fechados en `docs/` para
encontrar el comando y los archivos concretos de cada ejecución.
