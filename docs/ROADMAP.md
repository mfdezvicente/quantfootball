# Quant Football — Roadmap

## Implementación económica — 2026-10-15

- [x] Registro sellado de decisiones de abstención antes del cierre, sin backdating ni compra.
- [x] Panel unificado de registros, métricas probabilísticas, mercado, investigación y carencias de fuentes.
- [x] Neto/ROI liquidado, pendientes visibles, máxima caída y concentración del mayor premio.
- [x] Bootstrap por bloques de jornadas y estrés retirando el mayor cobro conservando su gasto.
- [x] Riesgo/cobro hasta 13 columnas, presupuesto máximo 10 €, manifiestos v2 y compatibilidad de v1 a 5 €.
- [x] Frontera exacta de sistemas de cobertura hasta 12 columnas, exportación simple en grupos 2–8.
- [x] Frontera monetaria de investigación con importe variable y opción no jugar; búsqueda heurística explícita.
- [x] Importador temporal de participaciones y motor de mezclas conjuntas de investigación.
- [x] Auditoría de fuentes económicas gratuitas y reglas actualmente enlazadas por SELAE.
- [x] Experimento separado de ascensos/calendario sobre 1.684 partidos; conservar el modelo actual.
- [x] CLI del ciclo 50/50 que genera/registera/adjunta cuotas y documenta fallos parciales.
- [x] Preparar J14 con tres divisiones, horarios cotejados y flujo de 10 €; sin registro oficial.
- [ ] Confirmar orden y cierre exacto J14 y registrar una pareja 50/50 con cuotas recientes.
- [ ] Reconstruir premios completos con redondeos y casos excepcionales en datos oficiales.
- [ ] Validar participación conjunta y previsión previa de recaudación/premios con datos gratuitos suficientes.
- [ ] Fijar un protocolo económico prospectivo propio cuando las dependencias anteriores estén resueltas.
- [ ] Acumular evidencia nueva de rentabilidad, estudiar un piloto y acordar su límite total de pérdidas.

Detalles: [PROFITABILITY_V1_20261015.md](PROFITABILITY_V1_20261015.md).

## Revisión exhaustiva J12 — 2026-10-14

- [x] Capturar resultados finales de Primera/Segunda y completar Córdoba–Tenerife de J11.
- [x] Guardar un histórico de 10.993 partidos, sin añadir Rayo–Athletic interrumpido ni fixtures futuros de Liga F.
- [x] Contrastar quince signos y seis premios de J12 en dos resúmenes independientes y mantener pendiente la verificación directa SELAE.
- [x] Evaluar las cinco estrategias originales: principal máximo nueve; robusta máximo diez; todas retorno condicionado cero.
- [x] Auditar partido a partido el coste de log loss, concentración de columnas, historial corto y discrepancia de cuotas/bandas.
- [x] Evaluar 27 partidos de boletos y 24 comparaciones únicas con cuotas, con una exclusión deportiva explícita.
- [x] Implementar la distinción entre encuentros abandonados/cancelados y resultados deportivos pendientes.
- [x] Preparar CLI, configuración y protocolo separado para un candidato fijo 50 % modelo/50 % mercado; J11/J12 excluidos de su validación prospectiva.
- [ ] Verificar el extracto oficial J12 y liquidar el registro completo de forma primaria.
- [ ] Generar y registrar una primera jornada futura del candidato con cuotas contemporáneas y previsión base fresca.
- [ ] Capturar cuotas de decisión/cierre y reducir el intervalo entre pronóstico y cierre.
- [ ] Evaluar transferencia de goles/fuerza de ascensos y calendario completo de clubes en temporadas separadas.
- [ ] Reunir porcentajes del público, recaudación/bote y premios para distinguir cobro, recuperación del gasto y beneficio.
- [ ] Demostrar mejora probabilística y rentabilidad en observaciones nuevas; conservar pérdidas y pendientes.

Detalles: [WEEKLY_20261014.md](WEEKLY_20261014.md). El candidato con cuotas está
preparado, no validado ni convertido en modelo principal. Los registros anteriores
permanecen intactos.

## Revisión de resultados y registro J12 — 2026-10-05

- [x] Evaluar 13 resultados finales de J11, mantener Córdoba–Tenerife pendiente y auditar las cinco estrategias congeladas.
- [x] Corregir el cruce de Sabadell–Andorra por su cambio de fecha, con coincidencia única y comprobación temporal.
- [x] Crear un refresco reutilizable de datasets que solo incorpora partidos finalizados anteriores al corte.
- [x] Crear un snapshot nuevo de 10.972 partidos sin modificar los históricos ni incluir resultados en directo.
- [x] Comparar modelo y mercado sobre los mismos ocho encuentros ya finalizados; mostrar el resultado desfavorable y el tamaño pequeño de la muestra.
- [x] Confirmar con la captura del usuario los quince partidos de J12 y registrarla antes del cierre.
- [x] Registrar el boleto completo de J12, seis columnas/4,50 €, Pleno y comparaciones probabilísticas de los catorce partidos con cuotas.
- [ ] Incorporar el último resultado deportivo de J11 cuando sea final y consultar los signos/premios oficiales publicados.
- [ ] Liquidar J12 con signos y premios oficiales después del último partido del 12 de octubre.
- [ ] Reunir porcentajes de selección del público capturados antes del cierre y datos de recaudación/bote para un estimador de rentabilidad.
- [ ] Comparar futuras versiones con el mercado en una cohorte nueva; el ajuste de parámetros sigue congelado.
- [ ] Demostrar rentabilidad positiva fuera de muestra antes de tratar las apuestas como inversión.

Detalles: [REVIEW_20261005.md](REVIEW_20261005.md). Todo el registro es simulado;
no se han realizado compras. Los apartados anteriores se conservan debajo
como historial del desarrollo.

## Cuotas y evaluación prospectiva — 2026-10-02

- [x] Conector de cuotas actuales de The Odds API para Primera y Segunda; cuota prevista máxima de dos créditos por captura.
- [x] Configuración local cifrada de credenciales y auditoría sin claves en logs.
- [x] Verificar orden y cierre del boleto de la jornada 11 y los horarios de sus catorce clubes.
- [x] Guardar el candidato y el modelo anterior antes del inicio en el estudio separado de probabilidades.
- [x] Registrar antes de resultados la exclusión del concurso completo por incluir selecciones fuera del alcance.
- [x] Evaluador de pares por competición y primera comparación válida con el mercado.
- [x] Configurar cuenta gratuita y completar la primera captura autenticada: 18 encuentros, 337 cotizaciones, dos créditos.
- [x] Cruzar identidades y horarios con LaLiga e incorporar el resultado terminado el 02-10 a un snapshot nuevo.
- [x] Guardar comparaciones modelo/mercado de encuentros antes de su inicio, separadas del cierre oficial y del ROI.
- [ ] Confirmar una fuente de cuotas para Liga F.
- [ ] Reunir resultados nuevos y evaluar modelos/cuotas sin cambiar parámetros.

Detalles: [THE_ODDS_API.md](THE_ODDS_API.md). La integración preparada no supone
que ya existan cuotas reales ni evidencia de ROI positivo. Las selecciones
nacionales quedan fuera del análisis acordado con el usuario.

## Current priority — Dynamic goals and temporal calibration (2026-10-02)

- [x] Joint penalized monthly attack/defence states with valid bounded low-score correction.
- [x] Compare three transition precisions and three temporal calibration modes.
- [x] Keep male incumbent models; select a 25% dynamic mixture for Liga F.
- [x] Integrate mixtures and frozen calibration into forecasts and bootstrap scenarios.
- [x] Show reliability curves, component comparisons and later-season diagnostics.
- [x] Save a frozen prospective protocol for future official contests under EUR 5.
- [ ] Obtain authorized timestamped odds for a same-match market benchmark.
- [ ] Register real future official contests and assess the new cohort without retuning.
- [ ] Acquire complete-calendar and representative shot/lineup data.
- [ ] Evaluate expected returns using reliable crowd-selection and payout information.

See [DYNAMIC_MODEL.md](DYNAMIC_MODEL.md). Current gains are retrospective; no new
dynamic-candidate ROI or real future contest registration has been produced.

## Current priority — Richer probabilities and portfolio risk (2026-09-25)

- [x] Derive 52 chronological form, venue, strength and league-recency predictors
- [x] Compare regularized logistic regression and gradient boosting candidates
- [x] Select mixtures on 2022–24 and report same-match 2024–26 diagnostics
- [x] Exact best-column hit distribution and 10+/11+/12+/13+/14+ probabilities
- [x] Compare expected and realized hit frequencies on the existing 61-contest cohort
- [ ] Confirm small probabilistic improvements on new prospective observations
- [ ] Add authorized timestamped market, lineup, injury or xG data where justified

See [FORM_AND_RISK.md](FORM_AND_RISK.md). Default model remains unchanged.

## Current priority — Timestamped market inputs and prospective registry (2026-09-25)

- [x] Expand official Sunday archive: 61 eligible contests, 36 exclusions logged
- [x] Evaluate promotion/relegation transfer candidate; retain baseline default
- [x] Import timestamped authorized odds and distinguish them from crowd shares
- [x] Add market comparison tab with explicit missing-data state
- [x] Local pre-deadline paper registry with frozen primary strategy and budget
- [x] Append-only settlement from official signs; pending/invalid records remain visible
- [ ] Acquire authorized real odds/crowd archive and evaluate matched fixtures
- [ ] Verify a future official coupon and deadline, then register before kickoff
- [ ] External trusted timestamps and continuous source monitoring
- [ ] Demonstrate positive expected return on genuinely new observations

See [MARKET_AND_REGISTRY.md](MARKET_AND_REGISTRY.md). No real odds were imported
and no future real contest was registered in this iteration. Earlier milestones
below are retained as development history.

## Current priority — Primera/Segunda research (2026-09-25)

- [x] Audit 22 complete division-seasons and recover missing results
- [x] Select and evaluate models separately for Primera and Segunda
- [x] Week-block bootstrap uncertainty and four budgeted coverage strategies
- [x] Import an eight-Sunday official window; seven in-scope coupons settled
- [x] Standalone HTML explorer, frozen mixed-division forecasts and JSON export
- [x] 70 Python tests and 168 dashboard state checks pass in the repository
- [ ] Visual browser review of the HTML (local-file access blocked by browser policy)
- [ ] Several complete seasons of official coupons, publication times and prizes
- [ ] Prospective predictions and promotion/relegation strength transfer
- [ ] Pre-close market/crowd inputs and evidence of positive expected return

See [SPAIN_MODEL.md](SPAIN_MODEL.md). The older milestones below record the previous state.

## Current priority — Quiniela V0 (2026-09-24)
- [x] Confirm objective: 14-result coverage, default maximum budget EUR 5
- [x] Exact complete-system and individual-column optimizers
- [x] Elo forecasts frozen at the coupon submission date
- [x] CLI, reproducible JSON snapshots and optimizer regression tests
- [x] Time-decayed regularized goal model, Dixon-Coles correction and Elo ensemble
- [x] Validation-only configuration selection and 750-match holdout evaluation
- [x] Optional Pleno al 15 goal-category forecast
- [ ] Complete/audit Primera and Segunda historical coverage
- [ ] Import official coupons and submission deadlines
- [ ] Evaluate historical coupons with a common cutoff and calibrated forecasts
- [ ] Produce and validate complete real contest plans from official fixtures
- [ ] Add expected returns when selection and prize data are reliable

Implementation and limitations: [QUINIELA.md](QUINIELA.md).
The milestones below retain the longer-term platform plan.

## QF-M0 — Foundations
- [x] QF-001 Repository foundations
- [x] QF-002 Data source audit
- [x] QF-003 Select LaLiga V0 dataset
- [x] QF-004 Build reproducible ingestion pipeline

## QF-M1 — Data Engine
Clean historical LaLiga match dataset.

## QF-M2 — Baseline Match Models
Naive → Elo → Poisson → Dixon-Coles.

## QF-M3 — Evaluation Engine
Walk-forward evaluation, Brier score, log loss and calibration.

## QF-M4 — Quant Match Engine
Selected/ensemble model, future probabilities and model versioning.

## QF-M5 — Market Engine
Odds, no-vig probabilities, model-market disagreement and CLV where possible.

## QF-M6 — Product V1
LaLiga dashboard, match pages, model track record and What Changed?

## Later
Player Intelligence, Investing-style player pages, Fantasy, screeners, what-if simulations and additional leagues.

## Research update — 2026-10-02

- [x] Audit six full Liga F seasons and isolate women's identities.
- [x] Update current Segunda results while preserving evaluation datasets.
- [x] Compare 116 features, boosting and fully converged neural challengers.
- [x] Select across prior/new candidates using chronological validation only.
- [x] Add exact allocation frontiers for P(14) and complete-system P(≥10).
- [x] Show mixed historical forecasts and compare allocations on all 61 eligible official contests.
- [ ] Obtain representative shot/xG, lineup and injury data with verifiable timestamps and suitable access.
- [ ] Record actual future mixed contests before kickoff and evaluate them without changing the frozen selection.
- [ ] Establish a reliable public-selection archive before fitting expected returns.

Evidence and limitations: [RESEARCH_20261002.md](RESEARCH_20261002.md).
