# Quant Football

## Investigación económica y presupuesto hasta 10 € — 15-10-2026

Registro de abstenciones prospectivas y panel unificado, cálculos conjuntos hasta
13 columnas/9,75 €, frontera económica hipotética y auditoría de fuentes gratuitas.
Los manifiestos originales mantienen el límite de 5 €; los nuevos de versión 2
pueden declarar un máximo de 10 €. La comparación 50/50 sigue con su protocolo
original. Ninguna compra automática ni rentabilidad positiva demostrada.

El experimento de ascensos/calendario sobre 1.684 partidos no superó al modelo
actual. Se generó una preparación de J14 con cuatro encuentros de Liga F; su
registro depende de confirmar el orden y cierre oficial.

- [Implementación, resultados, comandos y pendientes](PROFITABILITY_V1_20261015.md).
- Panel: `outputs/reports/profitability_v1_20261015/dashboard.html`.
- Registro económico: `python scripts/economic_registry.py --help`.
- Ciclo prospectivo: `python scripts/run_prospective_cycle.py --help`.

## Análisis semanal J12 — 14-10-2026

La estrategia principal guardada obtuvo **8, 8, 9, 7, 9 y 7 aciertos**: retorno
simulado condicionado **0 €**, neto **−4,50 €**. El sistema robusto llegó a diez
y tampoco cobró según dos resúmenes independientes concordantes. La verificación
primaria del escrutinio SELAE permanece pendiente por restricción geográfica.

Rayo–Athletic consta como interrumpido en LaLiga: su signo de Quiniela se usa
para el recuento condicionado, pero el partido se excluye del entrenamiento y
de las métricas deportivas. La nueva evaluación distingue exclusiones de
pendientes. Dataset nuevo: **10.993 partidos**, 21 añadidos.

En los trece partidos completos de J12 el log loss fue **0,8951 del modelo**
frente a **0,8394 del mercado**. La mezcla fija 50 % obtiene 0,8651 como
diagnóstico retrospectivo, sin validación prospectiva. Se deja un candidato
separado y un protocolo futuro para evaluar esa mezcla; el modelo principal
no se sustituye por el resultado de esta jornada.

- Informe visual: `outputs/reports/weekly_j12_20261014/dashboard.html`.
- [Análisis detallado, límites y prioridades](WEEKLY_20261014.md).
- Candidato preparado: `python scripts/plan_market_pool.py --help`.
- Los resultados no demuestran ROI esperado positivo.

## Revisión y siguiente simulación — 05-10-2026

Se han evaluado **13 de los 14 partidos** de la jornada 11 con resultados
deportivos finales. Córdoba–Tenerife seguía en juego en la captura. La propuesta
de doble + triple ya no puede alcanzar diez aciertos; pérdida simulada
condicionada a los signos oficiales: **4,50 €**. El ROI oficial sigue pendiente
y este concurso completo está excluido por el Pleno de selecciones.

Se corrige el cruce de partidos que cambiaron de fecha y se añade un refresco
reutilizable que excluye marcadores en directo. Nuevo snapshot: **10.972
resultados**, 17 incorporados. En ocho encuentros con resultado y cuotas,
el mercado obtiene mejor log loss que el modelo; no se ajustan parámetros con
esta muestra pequeña.

La captura del usuario confirma los quince partidos de la jornada 12. Se ha
registrado antes del cierre una simulación completa con **seis columnas por
4,50 €**, Pleno Real Madrid–Villarreal y cuotas reales en los primeros catorce
partidos. Cierre publicado: **10 de octubre, 14:00, hora de Madrid**. No se ha
realizado ninguna compra ni demostrado ROI esperado positivo.

- Revisión: `outputs/reports/j11_review_20261005/dashboard.html`.
- Propuesta completa J12: `outputs/predictions/registry/2026_j12/dashboard.html`.
- Comparación con cuotas: `outputs/predictions/market_matches/20261005_j12/dashboard.html`.
- [Resultados, correcciones y comandos](REVIEW_20261005.md).

## Cuotas reales — 03-10-2026

The Odds API está activo: primera captura de **18 encuentros y 337 cotizaciones**,
nueve de Primera y nueve de Segunda; consumo de dos créditos y saldo de 498.
Las identidades y los horarios coinciden con el calendario oficial. Se añade
un resultado de ayer a un snapshot nuevo de 10.955 partidos, conservando los
datasets y pronósticos anteriores. Liga F no figura en el catálogo autenticado.

El visor `outputs/predictions/market_matches/20261003_first_live/dashboard.html`
compara las probabilidades congeladas con el mercado antes del inicio de cada
encuentro. Los resultados siguen pendientes; no demuestra una ventaja ni ROI
positivo. Esta captura llegó después del cierre de la jornada 11 y no se anexa
como si hubiera estado disponible antes. [Detalles](THE_ODDS_API.md).

## Quiniela — actualización 02-10-2026

**Primera + Segunda + Liga F, comparación de modelos y asignación exacta bajo 5 €.**
10.954 resultados en el snapshot actual: 9.408 masculinos y 1.546 femeninos,
con 28 temporadas completas de competición. El dataset masculino original se
conserva para reproducir los experimentos anteriores.
Se han comparado 116 variables, regresiones, árboles y redes neuronales con
validación temporal. La mejora masculina sigue siendo pequeña e incierta;
las redes no fueron seleccionadas. Liga F tiene un modelo de goles propio.
El análisis de **61 concursos** sigue mostrando ROI negativo, también al
optimizar la probabilidad de alcanzar al menos diez aciertos.

- Visor histórico actualizado: `outputs/reports/allocations_v1/dashboard.html`.
- Ejemplo mixto con Liga F: `outputs/reports/mixed_demo_v1/dashboard.html`.
- Dinámica y calibración: `outputs/reports/dynamic_calibration_v1/dashboard.html`.
- Nuevo ejemplo mixto: `outputs/reports/mixed_dynamic_demo_v2/dashboard.html`.
- Probabilidades de clubes guardadas antes del cierre: `outputs/predictions/probability_pairs/2026_j11/dashboard.html`.
- [Configurar The Odds API gratuito y empezar a reunir cuotas reales](THE_ODDS_API.md).
- [Fuerzas dinámicas, comparación con el candidato anterior y evaluación futura](DYNAMIC_MODEL.md).
- [Liga F, 116 variables, redes neuronales y asignación por objetivo](RESEARCH_20261002.md).
- [52 variables, modelos candidatos y evaluación del riesgo](FORM_AND_RISK.md).
- [Importar mercado y registrar pronósticos antes del cierre](MARKET_AND_REGISTRY.md).
- [Resultados de la ampliación, límites y comandos](RESEARCH_EXPANSION.md).
- [Modelo por división y auditoría del dataset](SPAIN_MODEL.md).
- Generación: `python scripts/plan_spain.py --help`.
- Evaluación: `outputs/reports/spain_v5/evaluation.json`.

El texto siguiente conserva el contexto de la versión inicial; sus cifras de
Primera y carencias de Segunda están sustituidas por el informe anterior.

**Quant Football** is a forward-looking quantitative football platform focused on turning football data into expectations, valuations and market intelligence.

> **Core question:** What happens next?

## Initial scope

Quant Football V0 starts with a rigorous LaLiga match forecasting engine:

1. Reproducible historical data pipeline.
2. Baseline models: naive, Elo, Poisson and Dixon-Coles.
3. Proper temporal validation and calibration.
4. Immutable prediction tracking.
5. Later: market comparison, player intelligence, Fantasy and valuation.

## Principles

- No temporal leakage.
- Baselines before complexity.
- Probabilities must be calibrated and evaluated.
- Notebooks are for exploration; production logic belongs in `src/`.
- Public predictions are stored before outcomes are known.
- Features are added only when they answer a real user question.

Current milestone: **Quiniela V0 — Budgeted coverage**.

## Current product goal

Build a Quiniela planner with a default budget of **EUR 5 per contest**. First,
maximize estimated 14-result coverage using singles, doubles and triples, and
compare that with the most probable individual columns. Add expected returns
when reliable public-selection and prize data become available.

The first planner is implemented. It assumes independent outcomes and consumes
either forecasts frozen before a submission date or supplied probabilities.
The default experimental forecaster combines Elo and regularized Dixon-Coles,
selected on 2022-24 and evaluated on 750 matches from 2024-26. It also supports
an optional Pleno al 15 goal forecast. Prize returns are not modeled.

See [advanced model and held-out results](ADVANCED_MODEL.md).

See [Quiniela setup, data limitations and roadmap](QUINIELA.md).

```powershell
python -m pip install -e ".[dev]"
python scripts/plan_quiniela.py --probabilities examples/quiniela_demo.json --budget 5 --output outputs/predictions/demo_quiniela.json
```

The example uses fictional teams and probabilities, not an actual contest.
