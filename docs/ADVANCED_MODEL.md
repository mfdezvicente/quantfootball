# Modelo avanzado de Quiniela — QF-MATCH-004

## Qué está implementado

Un ensemble de Elo y un modelo de goles con ataque/defensa por equipo,
ventaja local, regularización y ponderación temporal. La configuración elegida
en validación usa 50% Elo y 50% Dixon–Coles, seguido de escalado de temperatura
de 0,9. Este ajuste de confianza no garantiza calibración perfecta.

El componente de goles usa una vida media de 365 días, penalización L2 de 10
y una ventana máxima de 1.461 días. La regularización reduce estimaciones
extremas en equipos con pocos datos; el decaimiento reduce el peso de resultados
antiguos. Las fortalezas modelan goles anotados y concedidos, además del resultado.

El ajuste se realiza en dos etapas: primero máxima verosimilitud Poisson
penalizada con gradiente analítico; después estimación acotada de rho para
corregir 0-0, 0-1, 1-0 y 1-1. Es una adaptación, no la estimación conjunta exacta
del artículo original. Los límites de rho garantizan probabilidades no negativas
en todos los emparejamientos conocidos y en el prior de equipo desconocido.

El 1X2 usa la distribución de diferencias de goles y la corrección de marcadores
bajos sin cortar la cola de goles. El Pleno devuelve las 16 combinaciones
0/1/2/M; M incorpora toda la probabilidad de tres o más goles. Su distribución
procede del componente Dixon–Coles, sin aplicar la mezcla Elo ni la temperatura
del 1X2. Por tanto, las dos salidas no son una única distribución conjunta calibrada.

## Selección y evaluación temporal

- Selección: 760 partidos de 2022-23 y 2023-24.
- Candidatos de goles: vidas medias 180/365 días y penalizaciones 2/10.
- Mezcla: pesos Dixon–Coles 0/0,5/1; temperaturas 0,9/1/1,1.
- Selección por log loss medio; configuración fijada antes de evaluar 2024-26.
- Evaluación final: 750 partidos de 2024-25 y 2025-26.
- Reentrenamiento cada lunes, utilizando exclusivamente fechas anteriores.
  Todos los partidos de esa semana comparten el estado congelado.
- Elo y naive usan el mismo corte semanal. Poisson comparte los parámetros
  de goles seleccionados y desactiva rho; no es un Poisson afinado por separado.
- El Elo con temperatura seleccionada en validación eligió 1,0 y coincide con
  el Elo original en la muestra final.

| Modelo | Log loss ↓ | Brier ↓ | Acierto 1X2 ↑ |
|---|---:|---:|---:|
| Naive | 1,059505 | 0,639360 | 46,80% |
| Elo | 0,983623 | 0,583102 | 52,67% |
| Poisson | 0,978852 | 0,580778 | 53,20% |
| Dixon–Coles | 0,979079 | 0,580903 | 53,20% |
| Ensemble seleccionado | **0,977513** | **0,579448** | **53,20%** |

La corrección Dixon–Coles aislada no mejora a Poisson en esta muestra.
Se mantiene la configuración elegida en validación; no se vuelve a seleccionar
mirando estos resultados finales. La mejora del ensemble frente a Elo es modesta:
0,006110 de log loss. Un bootstrap exploratorio de 2.000 remuestreos de 72 semanas
produce un intervalo 95% de [-0,010405, -0,001715] para ensemble menos Elo.
Ese intervalo no incorpora toda la incertidumbre del modelo ni demuestra rentabilidad.

El informe JSON incluye resultados por temporada, bins de fiabilidad por signo,
evaluación de las 16 categorías de goles sobre todos los partidos históricos,
predicciones individuales y hashes del código y dataset. Las categorías de goles
no se evaluaron sobre una selección histórica de partidos oficiales de Pleno al 15.

## Uso

El planificador usa el modelo avanzado por defecto al recibir `--fixtures`:

```powershell
python scripts/plan_quiniela.py --fixtures mi_jornada.json --cutoff 2026-09-24 --budget 5 --output outputs/predictions/jornada_avanzada.json
```

Para añadir el Pleno, proporcionar un JSON con `date`, `home_team`, `away_team`:

```powershell
python scripts/plan_quiniela.py --fixtures mi_jornada.json --pleno mi_pleno.json --cutoff 2026-09-24 --budget 5 --output outputs/predictions/jornada_con_pleno.json
```

El Pleno propone un único marcador para todas las columnas. El objetivo sigue
siendo la cobertura de los primeros 14 signos: no se optimiza una cartera que
repita los mismos 14 signos con distintos Plenos. La probabilidad de 14 más Pleno
se calcula suponiendo independencia del partido 15 respecto a los demás.

`--model elo` permite usar el benchmark anterior. `--model-config` permite cargar
otra configuración validada. Se rechazan cortes anteriores a `selected_before`
para evitar usar parámetros seleccionados con información futura.

Reproducir el experimento en un directorio nuevo:

```powershell
python scripts/evaluate_advanced.py --output-dir outputs/reports/mi_experimento
```

Artefactos locales de esta evaluación: `outputs/reports/advanced_v2/`.
Configuración activa: `configs/quiniela_model.json`. La configuración guarda
hiperparámetros; las fortalezas se reestiman al preparar cada boleto.

## Límites y siguiente prioridad

El dataset sigue siendo de Primera y omite diez resultados de 2024-25. Los dos
partidos de evaluación con equipos sin historia reciente usan un prior neutral
y se contabilizan. El planificador real rechaza equipos desconocidos.

Los bloques semanales no reproducen boletos oficiales. Las fuentes históricas
pueden contener correcciones publicadas después de los encuentros. Faltan Segunda,
alineaciones, bajas, cuotas y porcentajes apostados. El acierto 1X2 de la tabla es
por partido, no la probabilidad de ganar una Quiniela. La cobertura combinada
sigue suponiendo independencia entre partidos; no se ha demostrado ROI positivo.

La prioridad siguiente es completar datos y concursos oficiales para validar
cobertura de boletos con presupuesto de 5 EUR y su Pleno.

## Referencias

- Dixon y Coles (1997), [Modelling Association Football Scores and Inefficiencies in the Football Betting Market](https://academic.oup.com/jrsssc/article-abstract/46/2/265/6990546).
- Michels, Ötting y Karlis (2023), [Extending the Dixon and Coles model](https://arxiv.org/abs/2307.02139), descripción de la redistribución de los cuatro marcadores bajos.
- [SciPy: distribución Skellam](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.skellam.html).
