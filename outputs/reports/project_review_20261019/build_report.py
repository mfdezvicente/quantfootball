import json,hashlib,html
from pathlib import Path
from datetime import datetime,timezone
root=Path.cwd(); repo=Path('C:/Users/Usuario/GitHub/quantfootball')
audit=json.loads((root/'audit.json').read_text(encoding='utf-8'))
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
history=read(repo/'outputs/reports/allocations_v1/report.json')['summary']['individual_columns']
market=read(repo/'outputs/reports/weekly_j12_20261014/market_evaluation.json')
context=read(repo/'outputs/reports/context_research_v1/evaluation.json')
audit['review_created_at']=datetime.now(timezone.utc).isoformat()
audit['historical_roi_reference']={**{k:history[k] for k in ['coupons','cost_eur','gross_return_eur','net_eur','roi']},'cohort':'Historical stored 61-coupon strategy; separate from current prospective/economic cohorts'}
audit['market_comparison']=market['leagues']
audit['default_data_risks']=[{'script':'scripts/plan_spain.py','default_dataset':'data/processed/matches_spain.parquet','rows':9397,'last_date':'2026-09-20','scope':'men_only','default_config':'configs/quiniela_spain.json'}, {'script':'scripts/probability_registry.py evaluate','default_dataset':'data/processed/matches_quiniela_current.parquet','rows':10954,'last_date':'2026-09-28','scope':'mixed'}]
audit['source_hashes']={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [repo/'scripts/plan_spain.py',repo/'scripts/probability_registry.py',repo/'src/quantfootball/quiniela/decision.py',repo/'src/quantfootball/quiniela/economic_research.py',repo/'src/quantfootball/market/crowd.py',repo/'outputs/reports/context_research_v1/evaluation.json',repo/'outputs/reports/allocations_v1/report.json',repo/'outputs/reports/weekly_j12_20261014/market_evaluation.json']}
(root/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
report='''# Revisión integral del proyecto — 19 de octubre de 2026

La plataforma tiene una base de investigación y cálculo de coberturas desarrollada. La rentabilidad esperada positiva sigue sin demostrarse. La prioridad es completar el ciclo de datos, decisiones anteriores al cierre y liquidaciones, junto con el modelo económico que todavía falta.

## 1. Estado real por componente

| Componente | Evidencia encontrada | Evaluación |
|---|---|---|
| Datos deportivos | 10.993 resultados: 4.258 Primera, 5.181 Segunda, 1.554 Liga F | Utilizables; faltan incorporar nuevas jornadas al snapshot procesado |
| Modelos | Goles/Dixon–Coles, Elo, clasificadores de forma, dinámica femenina; experimentos de redes y calibración | Investigación amplia; ventaja sobre mercado no acreditada |
| Cuotas | Dos estudios existentes, 24 partidos únicos finalizados | Archivo demasiado pequeño; sin una primera pareja prospectiva del candidato 50/50 |
| Cobertura | Columnas, dobles/triples y riesgo conjunto, hasta 10 € | Cálculos implementados; objetivo principal P(14), distinto del beneficio esperado |
| Economía | Escenarios hipotéticos, mezcla conjunta pública y registro de abstención | Modelo de premios/participación sin validar; política operativa bloqueada en abstención |
| Operación | Un boleto completo J12 pendiente; dos pares J11/J12 válidos | Captura/registro semanal aún sin continuidad |

Se verificaron los sellos de los pares J11/J12 y la integridad contable del registro mediante su resumen. La última validación de implementación documentada fue de 83 pruebas; esta revisión no vuelve a ejecutar ni ampliar esa batería. Se inspeccionaron 48 módulos Python, 44 scripts y 13 archivos de pruebas. Estos conteos describen la implementación y no prueban calidad económica.

## 2. Datos: actualización y valores predeterminados

El snapshot procesado más reciente sigue siendo `matches_quiniela_20261014.parquet`. Sus últimos partidos son del 12 de octubre en ambas divisiones masculinas y del 4 de octubre en Liga F. En esta revisión se capturaron páginas primarias de LaLiga con 27 encuentros finalizados adicionales y dos en juego, sin modificar el dataset ni incluir marcadores en directo como resultados finales.

Hay un riesgo de usar versiones antiguas por omisión:

- `plan_spain.py` utiliza por defecto `matches_spain.parquet`: 9.397 encuentros, hasta el 20 de septiembre, sin Liga F. Su configuración predeterminada también es la antigua de España.
- `probability_registry.py evaluate` usa `matches_quiniela_current.parquet`: 10.954 encuentros, hasta el 28 de septiembre.
- El ciclo prospectivo exige dataset explícito y la configuración actual, pero no centraliza todavía la comprobación de frescura y alcance de todas las herramientas.

La mejora debe ser un manifiesto activo de datos/configuración, comprobado antes de cada ejecución. Los snapshots históricos deben permanecer identificados por hash para reproducirlos; no conviene cambiar silenciosamente un archivo histórico bajo el mismo nombre.

## 3. Qué dicen los resultados disponibles

### Simulaciones y registro completo

La simulación histórica guardada de 61 concursos, para columnas individuales, registra 274,50 € de coste y 120,08 € de cobro: −154,42 € y ROI −56,26 %. Corresponde a otra cohorte y condiciones históricas; no es el ROI validado del candidato nuevo ni de una estrategia económica activa. Es una evidencia adversa que debe conservarse.

J12 sigue pendiente de liquidación oficial en el registro. La revisión secundaria anterior indicaba cero cobro para las cinco carteras; la cartera principal obtuvo como máximo nueve aciertos. Una liquidación pendiente no debe aparecer como ROI cero, ni una revisión secundaria como recibo oficial.

### Calidad frente al mercado

| División | Partidos comparables | Log loss modelo | Log loss mercado |
|---|---:|---:|---:|
| Primera | 9 | 0,8634 | 0,8112 |
| Segunda | 15 | 1,0377 | 0,9918 |

Menor log loss indica mejor asignación de probabilidades. El mercado sale mejor en esta muestra, pequeña y concentrada en pocas jornadas. En Segunda, nuestro modelo acierta más favoritos que el mercado en esos quince partidos, pero asigna peor las probabilidades: el porcentaje de aciertos por sí solo no basta.

La mezcla 50/50 está preparada y tiene protocolo hasta el 1 de julio de 2027, pero no hay directorios registrados en su cohorte. Tampoco hay decisiones económicas registradas. La existencia de las herramientas no equivale a disponer ya de evidencia nueva.

### Experimento de variables nuevas

Las variables de ascensos y calendario no superaron al modelo actual. La variante de ascensos mejora mínimamente frente a su clasificador base en Primera, con un intervalo por semanas que contiene cero. El calendario añadido empeora en ambas divisiones. Se debe conservar el modelo actual.

Esta conclusión se limita al experimento: factores de transferencia fijados, calendario solo de liga y clasificador estático dentro de cada periodo. Un siguiente ensayo debe comparar los mismos partidos, ventanas y frecuencia de actualización. El resultado no descarta cualquier modelo jerárquico futuro ni demuestra que disponer de calendario completo carezca de valor. Las temporadas 2024–2026 ya se habían inspeccionado; se usarán como diagnóstico y desarrollo, no como una prueba final nueva.

## 4. Nueva comprobación de J14

Se contrastaron las quince identidades con sus IDs y horarios en las páginas primarias de LaLiga. Los catorce partidos combinables estaban finalizados. En la captura de las 21:20, hora de Madrid, Getafe–Rayo seguía en la primera parte; su marcador en directo no se liquida como definitivo.

La preparación guardada el 15 de octubre tenía presupuesto máximo 10 €, corte de entrenamiento 14 de octubre y estado provisional sin registro. No se incorpora retroactivamente al registro ni a la cohorte del 50/50.

| División | Partidos | Favoritos acertados | Log loss |
|---|---:|---:|---:|
| Primera | 7 | 5 | 0,8463 |
| Segunda | 3 | 1 | 1,0848 |
| Liga F | 4 | 4 | 0,5204 |
| Total | 14 | 10 | 0,8043 |

| Estrategia guardada | Coste previsto | Máximo de aciertos |
|---|---:|---:|
| Sistema completo | 9,00 € | 10 |
| Columnas individuales | 9,75 € | 11 |
| Sistema completo robusto | 9,00 € | 11 |
| Columnas robustas | 9,75 € | 11 |
| Sistema para P(≥10) | 9,00 € | 10 |

En las trece columnas individuales hay tres de once, cuatro de diez y seis de nueve. Su cobro hipotético depende de los premios oficiales: `3 × premio11 + 4 × premio10`. Si el de diez fuese cero, haría falta más de 3,25 € por premio de once para superar el coste de 9,75 €. No hay una apuesta comprada ni un ROI prospectivo que atribuir a este cálculo.

Los errores de favorito fueron Villarreal–Elche, Valencia–Athletic, Eibar–Mallorca y Las Palmas–Castellón. El empate de Villarreal tenía probabilidad 16,17 %, frente a un 70,53 % de victoria local: es un caso para auditar confianza y contexto, sin recalibrar todo el modelo para corregir una sola sorpresa.

Los cuatro aciertos femeninos no permiten concluir superioridad en Liga F. Tampoco se puede atribuir el mejor número de aciertos frente a J12 a una mejora de modelo: cambian partidos y presupuesto.

## 5. Limitaciones que debemos resolver

1. **Operación incompleta.** Se producen informes, pero faltan decisiones comparables registradas cada jornada. Un bloqueo de fuente debe dar lugar a un estado explícito y a conservar los datos deportivos útiles; no a perder toda la observación de la semana.
2. **Datos y configuración dispersos.** Hay herramientas con valores predeterminados antiguos, ficheros históricos y documentación que acumula estados de distintas fechas.
3. **Economía aún sin estimar.** `decision.py` devuelve siempre abstención mientras mantiene sus tres bloqueos; no está calculando y rechazando cada apuesta por valor negativo. `economic_research.py` usa premios fijos y un conjunto heurístico de carteras, sin Pleno, impuestos o reparto dependiente del resultado.
4. **Participación conjunta no identificada.** `market/crowd.py` puede representar mezclas, pero los componentes y pesos no se han estimado con un archivo representativo. Marginales de cada partido no identifican cuántos jugadores comparten una columna completa.
5. **Incertidumbre parcial.** El bootstrap mide sensibilidad a parte del entrenamiento; no incluye todas las fuentes de error, incertidumbre de mercado o cambios de alineación. Ocho remuestreos en J14 sirvieron para una preparación técnica, no para intervalos estables.
6. **Alcance de la búsqueda.** P(14) y algunas composiciones completas tienen solución exacta bajo los supuestos del modelo; la optimización del dinero no es globalmente exacta. Sistemas reducidos amplios y distribución del presupuesto entre distintos Plenos siguen sin desarrollarse.
7. **Evaluación expuesta a selección.** Varias familias y temporadas ya se han inspeccionado. Los nuevos cambios necesitan protocolo, comparadores y resultados posteriores; no elegiremos la cartera que más cobró en una jornada terminada.

## 6. Orden de mejora propuesto

| Prioridad | Trabajo concreto | Criterio de entrega |
|---|---|---|
| P0 · siguiente ciclo elegible | Cerrar el diagnóstico deportivo de J14, mantener su exclusión financiera, confirmar el próximo boleto y ejecutar una primera pareja base/50/50 con cuotas anteriores al cierre | Registro válido o abstención/fallo explícito para cada concurso; ningún registro retroactivo |
| P0 · datos | Añadir resultados realmente finalizados a un snapshot nuevo y centralizar manifiesto de dataset/configuración | Antes de pronosticar: fechas, divisiones, hashes, cobertura y frescura comprobados; históricos reproducibles |
| P1 · evaluación | Cuadro único con base, mercado y 50/50 sobre los mismos encuentros y por competición | Log loss, Brier, calibración y tamaño de muestra; 200 partidos como revisión diagnóstica, no prueba automática de rentabilidad |
| P1 · premios | Recopilar gratuitamente tablas oficiales, reglas, recaudación/bote, acertantes y porcentajes publicados, con fechas de captura | Reconstruir escrutinios normales y excepcionales y comprobar redondeos antes de habilitar una estimación económica |
| P2 · modelo | Investigar transferencia jerárquica de ataque/defensa y calendario completo con el mismo ciclo de entrenamiento que el comparador | Cada grupo de variables se prueba por separado; no cambiar el modelo por J14 ni por una única métrica favorable |
| P2 · valor económico | Modelar participación conjunta y número aleatorio de acertantes; simular reparto y escenarios de incertidumbre | Retorno condicionado al resultado, Pleno y nuestra participación en el reparto; permitir abstención cuando falte evidencia |
| P3 · carteras | Buscar carteras por beneficio conservador e importe variable, con comparadores de igual coste | Diferenciar exactitud del evaluador y optimalidad de la búsqueda; no gastar automáticamente el máximo |
| P3 · validación y piloto | Protocolo económico nuevo cuando el modelo de premios sea utilizable; seguimiento de ganancias, pérdidas y dependencia del mayor premio | Evidencia posterior al protocolo y límite acumulado de pérdidas acordado antes de un piloto real |

La investigación probabilística y la recopilación económica pueden avanzar mientras se acumulan resultados. La promoción de modelos y el uso económico deben depender de las comprobaciones anteriores. No añadimos una fecha prometida para conseguir ROI positivo.

## 7. Recomendación

Mantener el presupuesto como límite, usar simulación y abstención por falta de evidencia económica, y dedicar el siguiente bloque de desarrollo al ciclo operativo y a datos de premios/público. La mejora probabilística seguirá con comparaciones controladas. Una nueva red neuronal o más triples tienen una prioridad menor que resolver estas dependencias.

Fuentes deportivas capturadas: [Primera](https://www.laliga.com/laliga-easports/resultados/2026-27/jornada-9), [Segunda](https://www.laliga.com/laliga-hypermotion/resultados/2026-27/jornada-10) y [Liga F](https://www.laliga.com/futbol-femenino/resultados/2026-27/jornada-7). El momento de captura y hashes están en los JSON de esta revisión. No se consultaron claves ni se consumieron créditos nuevos de The Odds API.
'''
(root/'REPORT.md').write_text(report,encoding='utf-8')
fixture_rows=''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in [f['position'],f['home_team']+' — '+f['away_team'],f['score'],f['favorite'],f['sign']])+'</tr>' for f in audit['j14']['fixtures'])
page='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>QuantFootball · Revisión integral 19 octubre</title><style>
body{font:16px/1.55 system-ui;background:#101b29;color:#e6edf5;margin:0}main{max-width:1120px;margin:auto;padding:28px 20px}h1{font-size:32px}h2{margin-top:30px}p{color:#c3d1df}.notice{border-left:4px solid #efc270;background:#2a3038;padding:18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.card{padding:18px;background:#1c2b3d;border-radius:10px}.number{font-size:30px;color:#73dfbf}table{width:100%;border-collapse:collapse;background:#1b2a3b}td,th{text-align:left;padding:10px;border-bottom:1px solid #34455b}section{overflow-x:auto}a{color:#73dfbf}pre{white-space:pre-wrap;font:15px/1.7 system-ui;background:#172637;padding:20px}small{color:#bdcadd}
</style><main><h1>Estado del proyecto · 19 octubre 2026</h1><p>Plataforma de investigación desarrollada; ventaja económica pendiente de demostrar.</p>
<div class="notice"><strong>Prioridad: datos actualizados y decisiones anteriores al cierre.</strong><br>El candidato 50/50 tiene protocolo preparado y cero jornadas registradas. La política económica permanece en abstención por falta de modelos validados de participación y premios.</div>
<h2>Evidencia disponible</h2><div class="grid"><div class="card"><div class="number">10.993</div>Resultados en el último dataset procesado</div><div class="card"><div class="number">24</div>Comparaciones únicas con mercado</div><div class="card"><div class="number">0</div>Jornadas registradas del 50/50</div><div class="card"><div class="number">−56,26 %</div>ROI de la simulación histórica de 61 concursos; cohorte distinta</div></div>
<h2>J14 · diagnóstico de la preparación guardada</h2><p>Favoritos: 10 de 14. Trece columnas por 9,75 €: tres de once, cuatro de diez y seis de nueve. Preparación provisional sin registro: estos resultados no se incorporan al ROI prospectivo. El Pleno seguía en juego a las 21:20 en la captura.</p>
<section><table><tr><th>Posición</th><th>Partido</th><th>Resultado deportivo</th><th>Favorito</th><th>Signo deportivo</th></tr>'''+fixture_rows+'''</table></section>
<h2>Qué desarrollaremos primero</h2><ol><li>Actualizar datos y centralizar la selección del dataset/configuración.</li><li>Completar cada ciclo con registro válido o bloqueo documentado antes del cierre.</li><li>Comparar base, mercado y mezcla sin retocar el protocolo con los resultados.</li><li>Reconstruir premios e investigar participación pública antes de habilitar decisiones económicas.</li><li>Probar mejoras de modelo con comparadores equivalentes y evidencia posterior.</li></ol>
<p><a href="REPORT.md">Abrir análisis completo</a> · <a href="audit.json">Datos y evidencia de la revisión</a></p><details><summary>Análisis completo dentro del panel</summary><pre>'''+html.escape(report)+'''</pre></details><small>Consulta puntual del proyecto. Sin compras, nuevos créditos de cuotas ni registros retroactivos.</small></main></html>'''
(root/'dashboard.html').write_text(page,encoding='utf-8')
print('Written REPORT.md, dashboard.html and expanded audit.json')
