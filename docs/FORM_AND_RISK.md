# Variables de forma, modelos probabilísticos y riesgo del boleto

Actualización: 25-09-2026. Esta iteración responde a la petición de mejorar las
probabilidades usando más variables y evaluar su utilidad antes de adoptarlas.

## Datos y variables

Se generaron **52 predictores** a partir de los 9.397 partidos auditados de Primera
y Segunda. Son representaciones por equipo y sus diferencias; no 52 fuentes de
información independientes. Se conservan en
`outputs/reports/form_v1/features.parquet`, con el código reproducible en
`src/quantfootball/features/form.py`.

Incluyen:

- Goles a favor y en contra, puntos y frecuencia de empate en los últimos 5 y 20 partidos.
- Rendimiento en los últimos 20 partidos como local o visitante.
- Fuerza Elo compartida entre divisiones y fuerza de los rivales anteriores,
  calculadas antes de sus respectivos resultados.
- Cantidad de historial disponible y cambio de división respecto al último partido.
- Días desde el último partido de liga registrado, con transformación logarítmica.
- Diferencias entre local y visitante y un indicador de Primera/Segunda.

Las medias tienen una regularización hacia valores previos para reducir extremos
en equipos con pocos encuentros. La variable de días **no mide el descanso real
si hubo Copa, Europa u otros partidos fuera del dataset**. No se han incorporado
lesiones, alineaciones, xG ni cuotas sin una fuente temporal verificable.
No hizo falta descargar nuevos datos para esta primera ampliación de variables.

## Evaluación temporal

Las variables se congelan antes del lunes de cada semana. Los coeficientes se
reentrenan al primer lunes activo del mes con etiquetas anteriores a ese corte,
una ventana de seis años y una semivida de dos años para la ponderación temporal.
Se excluyen las dos primeras temporadas del entrenamiento del clasificador,
porque su historial inicial es incompleto.

Se compararon tres regresiones logísticas regularizadas y dos clasificadores
de gradient boosting con árboles. El escalado se ajusta únicamente en los datos
anteriores al corte. Los árboles no usan una validación aleatoria para detenerse.
Los pesos de mezcla y temperatura se seleccionan con 2022–24, incluyendo la
opción de conservar íntegro el modelo anterior.

La selección favoreció una **mezcla de 75 % del modelo anterior y 25 % de regresión
logística**, con distinta regularización por división. Los árboles no mejoraron
esa selección. Los resultados siguientes corresponden a los mismos 1.684 partidos
de 2024–26 ya inspeccionados previamente; **no son un nuevo holdout intacto**.

| División | N | Log loss anterior ↓ | Candidato ↓ | Acierto anterior | Candidato |
|---|---:|---:|---:|---:|---:|
| Primera | 760 | 0,97526 | 0,97297 | 53,29 % | 53,42 % |
| Segunda | 924 | 1,04705 | 1,04491 | 46,65 % | 46,54 % |

También mejora el Brier: 0,57785 → 0,57625 en Primera y 0,63030 → 0,62875 en Segunda.
La calidad de las probabilidades mejora ligeramente en promedio, pero el acierto
directo de Segunda baja un partido. No sería correcto afirmar que todo mejora.

Log loss y Brier valoran las probabilidades asignadas a los tres signos; cuanto
menores, mejor. El acierto directo cuenta los partidos en los que el signo con
mayor probabilidad coincide con el resultado. Para elegir dobles y triples interesa
también la calidad de las probabilidades de los otros signos.

La diferencia de log loss (candidato menos anterior) tiene estos intervalos
exploratorios del 95 %, remuestreando semanas:

- Primera: −0,00229; intervalo **[−0,00513; +0,00039]**.
- Segunda: −0,00215; intervalo **[−0,00500; +0,00077]**.

Ambos incluyen cero. **El candidato queda disponible de forma optativa** en
`configs/quiniela_form_candidate.json`; el modelo por defecto se mantiene.
La evaluación completa y el ranking de todos los candidatos están en
`outputs/reports/form_v1/evaluation.json`.

Los pronósticos del candidato vuelven a ajustar los coeficientes en los escenarios
de remuestreo. Las variables históricas de forma permanecen fijas dentro de ese
remuestreo: los intervalos no capturan toda la incertidumbre sobre esas variables.
El Pleno sigue dependiendo del modelo de goles anterior.

## Riesgo de las selecciones

Se añadió el cálculo **exacto, condicionado a las probabilidades del modelo**, de
la distribución del mejor número de aciertos entre hasta seis columnas.
Respeta que todas las columnas comparten los mismos resultados de los partidos.
Suponer independencia entre columnas inflaría la probabilidad de alcanzar premios.

El cálculo separa las posiciones donde todas las columnas eligen el mismo signo,
usa una distribución Poisson-binomial para ellas y enumera únicamente las posiciones
con signos diferentes. Después combina ambas distribuciones. En los 61 concursos,
los 850 portafolios distintos de los presupuestos analizados difieren en un máximo
de cinco posiciones, por lo que el cálculo es rápido y no necesita Monte Carlo.

El visor añade:

- Probabilidad de alcanzar al menos 10, 11, 12, 13 y 14 aciertos en alguna columna.
- Probabilidad de quedarse por debajo de diez en todas las columnas.
- Distribución y valor esperado del mejor número de aciertos.
- Sensibilidad de esas probabilidades al remuestreo de parámetros.

**10 aciertos no equivalen necesariamente a cobrar; cobrar no equivale a obtener
beneficio.** Hay categorías con premio unitario cero. No se deduce un ROI esperado
de estas probabilidades, y no se incluye el Pleno en su distribución.

Como diagnóstico de las selecciones del modelo anterior en los 61 concursos:

| Estrategia | Concursos 10+ esperados | Observados 10+ | Con cobro | Con beneficio neto |
|---|---:|---:|---:|---:|
| Dobles/triples | 12,71 | 10 | 10 | 3 |
| Columnas individuales | 12,52 | 9 | 8 | 5 |
| Dobles/triples conservadores | 12,51 | 9 | 9 | 3 |
| Columnas conservadoras | 12,50 | 9 | 7 | 3 |

Es un diagnóstico descriptivo sobre una muestra pequeña y condicionada por las
exclusiones del estudio anterior. No se ajustaron las selecciones para acercar
esas cifras ni se eligió una estrategia por su beneficio retrospectivo.

## Retorno del candidato

Se ha evaluado el candidato en los mismos **61 concursos** y con el mismo
coste de **274,50 € por estrategia**. Los pesos del modelo se eligieron por
log loss de validación, antes de consultar estos retornos.

| Estrategia | Premios anteriores (€) | Premios candidato (€) | ROI anterior | ROI candidato |
|---|---:|---:|---:|---:|
| Dobles/triples | 117,10 | 76,63 | -57,34 % | -72,08 % |
| Columnas individuales | 120,08 | 102,45 | -56,26 % | -62,68 % |
| Dobles/triples conservadores | 98,92 | 96,71 | -63,96 % | -64,77 % |
| Columnas conservadoras | 98,08 | 99,82 | -64,27 % | -63,64 % |

El resultado económico puede mejorar o empeorar según la selección: mejorar
ligeramente la calidad probabilística no basta para demostrar rentabilidad.
El visor del candidato está en `outputs/reports/official_form_v1/dashboard.html`;
el del modelo anterior, enriquecido con riesgo y comparación de modelos, en
`outputs/reports/portfolio_risk_v2/dashboard.html`.

La comparación pareada y sus intervalos descriptivos están en
`outputs/reports/official_form_v1/comparison_to_baseline.json`. Se mantienen
las mismas limitaciones sobre exclusiones, premios brutos, reparto contrafactual
y periodos ya inspeccionados. El ROI esperado positivo sigue sin demostrarse.

## Reproducir

Cada salida debe ser un directorio nuevo. Los archivos originales no se sobrescriben.

```powershell
python scripts/evaluate_form.py --baseline outputs/reports/spain_v5 --output-dir outputs/reports/form_nuevo
python scripts/plan_spain.py --fixtures examples/coupon_2025-05-25.json --pleno examples/pleno_2025-05-25.json --config configs/quiniela_form_candidate.json --cutoff 2025-05-23 --budget 5 --output-dir outputs/predictions/ejemplo_form
python scripts/analyze_portfolio_risk.py --report outputs/reports/official_expanded_v1/roi.json --output-dir outputs/reports/riesgo_nuevo
python scripts/backtest_official.py --config configs/quiniela_form_candidate.json --raw-dir data/raw/official_expanded --start 2024-08-04 --end 2026-06-07 --allow-cold-start --output-dir outputs/reports/concursos_form_nuevo
```

El ejemplo de pronóstico es histórico. Para evaluar una mejora real fuera de
muestra es necesario registrar un concurso futuro antes del cierre y mantener
congelada la configuración, como explica [MARKET_AND_REGISTRY.md](MARKET_AND_REGISTRY.md).
