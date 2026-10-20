# Cuotas actuales con The Odds API

Actualización: 03-10-2026. **Conexión autenticada y carga de la credencial cifrada
comprobadas.** La primera captura contiene 337 cotizaciones de 18 encuentros:
nueve de Primera y nueve de Segunda. Coste declarado: dos créditos; saldo tras
la captura: 498. Los modelos mantienen sus parámetros.

## Primera captura real y estudio de encuentros

- Archivo original: `data/raw/market_the_odds_api/20261003_first_live/`.
- Identidades revisadas: `data/raw/market_review_20261003/snapshot_reviewed.json`.
- Registro local previo a los inicios:
  `outputs/predictions/market_matches/20261003_first_live/dashboard.html`.
- Nuevo dataset: `data/processed/matches_quiniela_20261003.parquet`, 10.955 partidos.
  Incluye el encuentro terminado el 02-10; se excluye todo resultado fechado el
  03-10 o después del entrenamiento. El snapshot anterior queda conservado.

Los dieciocho nombres y horarios se cruzaron de forma única con los calendarios
oficiales de LaLiga. Se añadieron alias explícitos para Málaga, Alavés, Sabadell FC
y Andorra CF. La revisión reutiliza las respuestas almacenadas, sin otro consumo
de créditos ni cambios al archivo original.

La recuperación terminó el **03-10-2026 a las 14:04:53 de Madrid**, después del
cierre de la jornada 11 a las 14:00. No se adjunta al registro de esa jornada
como evidencia de mercado anterior al cierre. El nuevo estudio compara solo
encuentros individuales todavía no iniciados y queda separado del protocolo
de boletos completos y ROI.

```powershell
python scripts/forecast_market.py --snapshot data/raw/market_review_20261003/snapshot_reviewed.json --dataset data/processed/matches_quiniela_20261003.parquet --config configs/quiniela_dynamic_candidate.json --cutoff 2026-10-03 --draws 64 --output-dir outputs/predictions/market_matches/CAPTURA_NUEVA
python scripts/evaluate_market_studies.py --root outputs/predictions/market_matches --dataset DATASET_ACTUALIZADO.parquet --output outputs/reports/EVALUACION_NUEVA.json
```

La generación exige una carpeta nueva y rechaza cualquier registro cuando ya
haya comenzado alguno de los encuentros incluidos. Conserva configuración,
snapshot, pronósticos y huellas, con hora real. La evaluación posterior informa
log loss, Brier y precisión sobre los mismos partidos con cuotas, deduplicando
por primera predicción registrada. Los registros inválidos y los resultados
pendientes permanecen visibles. No se deduce significación, mezcla óptima o ROI
de los desacuerdos con el mercado.

## Activación local

1. Crear la cuenta **Starter gratuita** en [The Odds API](https://the-odds-api.com/).
2. En PowerShell, desde `C:\Users\Usuario\GitHub\quantfootball`, ejecutar:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/configure_odds_api.ps1
```

El script pide la clave con entrada oculta y la guarda cifrada con Windows DPAPI
para el perfil actual, en `data/raw/credentials/the_odds_api.dpapi`. Esa carpeta
está excluida de Git. No pasar la clave por argumentos ni pegarla en el chat.
`-Replace` permite actualizarla. Otro perfil/ordenador puede requerir configurarla
de nuevo. En otros sistemas se puede usar la variable privada `ODDS_API_KEY`.

Con el entorno Python del proyecto activado:

```powershell
python scripts/fetch_market_odds.py --status
python scripts/fetch_market_odds.py --check
python scripts/fetch_market_odds.py
```

`--status` es local. `--check` consulta catálogo y saldo sin consumir créditos.
La captura pide solo **EU + h2h** en decimal, una vez por liga: hasta **dos créditos
previstos por ejecución**. Comprueba saldo, conserva las cabeceras de consumo y
no reintenta peticiones fallidas. Si el consumo es inesperado o desconocido,
detiene las peticiones restantes. [Documentación v4](https://the-odds-api.com/liveapi/guides/v4/).

El plan gratuito publica **500 créditos al mes y no incluye cuotas históricas**.
Construiremos un archivo propio desde ahora. Una captura diaria de ambas ligas
supondría unos 60 créditos en treinta días si se mantienen estos costes. No hay
alta automática, compra ni peticiones a endpoints históricos.
[Plan oficial](https://the-odds-api.com/).

## Alcance acordado

| Competición de clubes | Modelo / dataset | Cuotas |
| --- | --- | --- |
| Primera masculina | Disponible | `soccer_spain_la_liga`, comprobar cobertura real |
| Segunda masculina | Disponible | `soccer_spain_segunda_division`, comprobar cobertura real |
| Primera femenina, Liga F | Disponible, separado de hombres | No aparece en el catálogo autenticado consultado el 03-10-2026 |
| Selecciones | Fuera del análisis acordado | No se solicitan |

Los [deportes del proveedor](https://the-odds-api.com/sports-odds-data/sports-apis.html)
identifican las dos ligas masculinas. El catálogo autenticado se conserva en cada
auditoría. No se inventan cuotas para competiciones ausentes ni se mezclan
categorías. El alcance confirmado es Primera y Segunda masculinas y Liga F;
las demás competiciones quedan fuera del estudio.

## Capturas y comparaciones

Cada ejecución crea `data/raw/market_the_odds_api/FECHA_UTC/` con respuestas
depuradas `es.1.json` y/o `es.2.json`, `snapshot.json` para el comparador y
`audit.json` con catálogo, alias, incidencias, cuota y huellas de los archivos.
Las URL y errores guardados omiten la clave. Los datos se identifican por nombres
de local, `Draw` y visitante, nunca por el orden del array. Se rechazan eventos
iniciados, cuotas del futuro y mercados sin tres resultados.

Cada casa conserva su fecha de actualización; el snapshot marca el final de
la adquisición secuencial, sin afirmar observación simultánea. Los cruces usan
competición, equipos y fecha local de Madrid. No hay emparejamiento difuso.
Se pueden añadir alias revisados con `--aliases`; también usar `--competitions
es.2`, `--from-time`, `--to-time` y `--output-dir` nuevo. La ventana máxima es
de catorce días.

Las [condiciones del proveedor](https://the-odds-api.com/terms-and-conditions.html)
permiten conservar datos, analizar y entrenar modelos; prohíben revender un feed
competidor. Esta fuente autoriza el uso previsto del proyecto.

```powershell
python scripts/compare_market.py --forecast outputs/reports/upcoming_j11_candidate_v1/forecast.json --snapshot data/raw/market_the_odds_api/CAPTURA/snapshot.json --decision-at MOMENTO_ISO_CON_ZONA --output-dir outputs/reports/j11_market_nuevo
```

Sustituir los marcadores por la captura y un momento real posterior a la
recuperación y a la creación del pronóstico, anterior al cierre/inicios. La
eliminación proporcional del margen es una aproximación. Las cuotas no contienen
popularidad de columnas de Quiniela ni premios esperados. No se ajusta una mezcla
con el modelo a partir de esta comparación.

## Registro de probabilidades de clubes

La jornada oficial 11 cierra el **03-10-2026 a las 14:00 de Madrid**; sus catorce
primeros partidos son diez de Segunda y cuatro de Liga F. El Pleno incluye
selecciones y queda fuera del alcance.
[Boleto oficial](https://juegos.loteriasyapuestas.es/jugar/la-quiniela/apuesta/?access=sched&lang=es).
Los horarios de clubes se contrastaron con
[Segunda, jornada 8](https://www.laliga.com/laliga-hypermotion/resultados/2026-27/jornada-8)
y [Liga F, jornada 6](https://www.laliga.com/futbol-femenino/resultados/2026-27/jornada-6).

Se guardan ambos pronósticos con 64 remuestreos, mismo dataset y corte 02-10-2026,
en `outputs/predictions/probability_pairs/2026_j11/`. El código de modelos y las
configuraciones siguen el protocolo anterior. **Es un estudio de probabilidades
de clubes, separado de los boletos completos del protocolo de ROI.** La exclusión
del concurso completo se anota antes de los resultados. El visor no es un boleto
completo para sellar y no se ha realizado una apuesta.

`scripts/probability_registry.py` congela ambos archivos, observación oficial,
protocolo y configuraciones, conservando hora local y SHA-256. No hay sello externo.
Una captura real antes del cierre puede adjuntarse:

```powershell
python scripts/probability_registry.py attach-market --record outputs/predictions/probability_pairs/2026_j11 --comparison outputs/reports/j11_market_nuevo/comparison.json
```

Se conserva la primera comparación válida y no se permite sustituirla. Si la
clave llega después del cierre, esa jornada conserva ausencia de mercado. No se
reconstruye una supuesta captura anterior. Tras incorporar resultados jugados:

```powershell
python scripts/probability_registry.py evaluate --output outputs/reports/probability_pairs_evaluacion_nueva.json
```

Informa log loss, Brier y precisión por competición, enumera registros inválidos
y pendientes y deduplica encuentros por primer pronóstico. Mercado y modelo se
miden sobre exactamente el mismo subconjunto. No se calcula ROI ni se usan los
resultados nuevos para ajustar parámetros. Los signos administrativos de la
Quiniela pertenecen a la evaluación separada de premios.

## Comprobaciones

Se comprobó la conexión real, el descifrado DPAPI y las dos peticiones de cuotas.
Se generaron pronósticos de encuentros y una evaluación inicial con resultados
pendientes. Se revisó Python, lint y sintaxis JavaScript. No se añadieron ni
ejecutaron pruebas unitarias; el HTML no se inspeccionó visualmente.
