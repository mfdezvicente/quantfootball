# Modelos flexibles y calibración contextual — 19 de octubre de 2026

Investigación histórica de periodos ya inspeccionados. El seguimiento de marcadores bajos se planteó después de ver la primera ronda y es adaptativo.

La evaluación final verifica 1716 ajustes semanales convergidos y 117 variantes guardadas.

| División | Modelo actual LL | Candidato elegido por 2023–24 | LL diagnóstico | Diferencia |
|---|---:|---|---:|---:|
| Primera masculina | 0.972316 | Binomial negativa + marcadores bajos (25%) · Temperatura | 0.971772 | -0.000544 |
| Segunda masculina | 1.044906 | Binomial negativa (100%) · Contextual | 1.049801 | +0.004895 |
| Liga F | 0.886576 | Poisson de control (100%) · Identidad | 0.894380 | +0.007804 |

Primera mejora muy poco y su intervalo incluye cero. Los candidatos elegidos para Segunda y Liga F empeoran. No se cambia el modelo de producción ni el protocolo prospectivo 50/50.

La sobredispersión estimada suele llegar al límite Poisson dentro de las familias y priors ensayados. La calibración contextual da mejoras puntuales de diagnóstico en Primera y Liga F y empeora en Segunda; no se promueve ninguna usando solo estos resultados.

El archivo source/ conserva el código exacto. initial_round/ conserva evaluación, protocolo, selección y código de la primera ronda. Los resultados de Pleno de los modelos de goles se evalúan por separado; las mezclas 1X2 no heredan esos indicadores.

## Reproducción

Usar el entorno del proyecto y una carpeta de salida nueva:

```
python scripts/evaluate_goal_flex_research.py --output-dir outputs/reports/goal_flex_replica --follow-up-to outputs/reports/goal_flex_20261019/initial_round/evaluation.json
```

## Límites
- These periods and baseline hyperparameters were already inspected; not fresh or fully nested confirmation
- 39 model/calibration candidates per competition; bootstrap intervals do not correct model selection
- Goal models use per-competition global shape; shared-tempo dependence is nonnegative only
- The optional NB low-score kernel is a separately fitted bounded Sarmanov-type correction; not original constant-rho Dixon-Coles
- Cold teams receive zero attack/defence prior; no new transfer, injuries, lineups or xG information
- Score-grid metrics concern standalone goal models; calibrated 1X2 mixtures do not inherit a joint goal grid
- No production promotion, future-market data, purchases or ROI claim

Los registros antiguos y la configuración congelada de producción se conservan. No se han usado créditos de cuotas ni se demuestra ventaja económica.