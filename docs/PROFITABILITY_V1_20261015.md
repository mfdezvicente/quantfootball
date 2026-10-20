# Implementación de investigación económica — 15 de octubre de 2026

El presupuesto máximo acordado pasa a 10 € y se permite no jugar. La simulación sigue siendo el modo operativo. El sistema aún no dispone de evidencia de rentabilidad positiva.

## Entregado y ejecutado

| Bloque del plan | Implementación | Estado |
|---|---|---|
| Registro unificado | Panel de decisiones, probabilidades por competición, cuotas, investigación y disponibilidad de fuentes | Ejecutado sobre los registros existentes |
| Abstención | Registro anterior al cierre, importe cero, causas y archivos sellados; rechaza ejemplos, horarios futuros, jornadas cerradas y entradas alteradas | Implementado y probado; ninguna abstención real retroactiva |
| Seguimiento | Neto, ROI liquidado, máxima caída, concentración del mayor premio y estrés retirando ese cobro | Implementado; J12 continúa pendiente de liquidación oficial |
| Validación económica | Bootstrap de bloques de cuatro jornadas, 5.000 réplicas, disponible desde ocho liquidaciones | Implementado como diagnóstico; no demuestra una ventaja ni cubre premios nunca observados |
| Hasta 10 € | Riesgo/cobro conjuntos hasta trece columnas; sistemas de 2, 3, 4, 6, 8, 9 y 12 columnas | Implementado y probado |
| Importe variable | Frontera de candidatos de cobertura con estrés de premios y opción cero | Ejecutada como investigación hipotética; búsqueda heurística para dinero |
| Ascensos/calendario | Cuatro variantes con grupos separados y selección temporal | Ejecutado sobre 1.684 partidos; ninguna sustituye al modelo actual |
| Participación pública | Importador con fechas y separación de cuotas; distribución conjunta mediante mezclas explícitas | Implementado; faltan datos para estimar y validar los componentes |
| Modelo de premios | Auditoría de reglas y fuentes; escenarios fijos ya disponibles | Dependiente de reconstrucción y datos económicos fiables, todavía bloqueado |
| Ciclo 50/50 | CLI que genera base/mezcla, registra pareja y adjunta cuotas; audita fallos parciales | Preparado; requiere boleto y cierre verificados, más snapshot actual |
| J14 | Quince identidades/horarios cotejados con LaLiga; pronóstico preliminar de 10 € | Generado sin registro; orden directo/cierre oficial pendientes |

## Compatibilidad del presupuesto y formularios

Los manifiestos completos de versión 1 mantienen el máximo de 5 €. Para nuevos registros completos de hasta 10 € debe usarse `schema_version: 2`, `maximum_budget_eur: 10` y `official_order_verified: true`. El coste real se calcula por las columnas, no por el máximo disponible. Trece columnas cuestan 9,75 €, dejando 0,25 €.

La ayuda actual de SELAE describe hasta ocho apuestas simples por formulario. La exportación divide nueve columnas en 7+2 y trece en 8+5; no deja un formulario de una apuesta. Los sistemas completos pueden formularse mediante múltiples. La exportación organiza las columnas, sin transmitir una compra ni certificar aceptación del canal. No incluye Elige8 ni diversificación del Pleno entre columnas.

Se amplía la optimización exacta de P(mejor columna ≥10) para todas las composiciones completas hasta trece columnas. También se mantiene la optimización exacta de P(14) bajo independencia entre partidos. La incertidumbre de estimación y la incertidumbre del resultado permanecen distintas.

## Investigación de ascensos y calendario

Se emplea el mismo clasificador logístico fijo C=0,1 para cuatro variantes: variables existentes; nuevas variables de transición entre divisiones; nuevas variables de calendario; ambas. Se entrena antes de julio de 2022 para seleccionar en 2022–2024 y se vuelve a entrenar antes de julio de 2024 para diagnosticar 2024–2026. El modelo se mantiene fijo dentro de cada periodo.

| Variante | Log loss Primera, 760 partidos | Log loss Segunda, 924 partidos |
|---|---:|---:|
| Clasificador base del experimento | 1,0115 | 1,0772 |
| Añadir transición entre divisiones | 1,0106 | 1,0780 |
| Añadir calendario | 1,0174 | 1,0807 |
| Añadir ambos | 1,0167 | 1,0816 |
| Modelo actual de referencia | 0,9723 | 1,0449 |

La validación eligió la variante base en ambas competiciones. La diferencia de ascensos frente al clasificador base de Primera tiene un intervalo por semanas que contiene cero. Todas las variantes empeoran frente al modelo actual. El resultado justifica conservarlo; no demuestra que cualquier tratamiento futuro de ascensos o calendario carezca de utilidad.

Los periodos 2024–2026 se habían inspeccionado en investigaciones anteriores: este diagnóstico no es confirmación nueva. El calendario contiene solo liga y utiliza fechas finales archivadas, no un archivo de publicaciones contemporáneas. La cadencia de entrenamiento también difiere de la del modelo actual. No se mezclan mujeres con hombres en este experimento.

## Economía: qué está habilitado

`economic_registry.py register` guarda abstenciones prospectivas y sus causas. Exige un boleto confirmado, captura anterior al registro, cierre y quince inicios posteriores. Puede conservar un concurso fuera del alcance como abstención; no intenta generar probabilidades de selecciones o competiciones no auditadas.

El informe de decisión versionado contiene acción, razones, máximo, gasto, columnas, modelo, hashes de datos y campos económicos. Las estimaciones económicas desconocidas permanecen `null`, en lugar de fingir ceros o beneficios. `economic_registry.py verify` coteja archivos y recalcula la política de abstención vigente de esta versión.

`optimize_economic_research.py` compara importes de 1,50 a 9,75 € y cero sobre candidatos de P(14). Evalúa exactamente la esperanza de cada cartera para tablas fijas y calcula el cobro conjunto del ganador hipotético. La búsqueda monetaria no es globalmente óptima. Los escenarios de premios no identifican premios futuros: siempre se conserva `deployment_action: abstain` mientras no exista un modelo económico validado y un protocolo propio.

En el ejemplo retrospectivo J12 con premios ×0,5, ×1 y ×2, la frontera de veinte candidatos eligió no apostar bajo el mínimo de los tres retornos condicionados. No se cuenta como una decisión hecha antes de J12 ni se utiliza para rehacer su pérdida observada.

La mezcla conjunta de participación puede expresar correlación entre los signos elegidos por una misma persona. Dos mezclas con los mismos marginales pueden dar probabilidades de columnas y de premios distintas. Por eso el importador no identifica una distribución conjunta a partir de catorce porcentajes aislados.

## Fuentes y bloqueos concretos

- La ayuda de SELAE enlaza actualmente un PDF de reglas de octubre de 2019: documenta reparto, mínimos y transferencias entre categorías. Falta validar la reconstrucción completa y el redondeo en escrutinios reales antes de desplegar un modelo de premios.
- Se localizaron documentos oficiales con participaciones marginales, recaudación, acertantes y premios. Son ejemplos históricos; faltan un archivo representativo y capturas anteriores al cierre. Descargarlos hoy no los convierte en datos disponibles históricamente para esta aplicación.
- The Odds API confirma las competiciones masculinas utilizadas; no se confirmó una competición doméstica española femenina en el catálogo revisado. No se consumieron créditos nuevos en esta iteración.
- Para J14, el orden coincide en varios listados públicos de administraciones y los quince partidos tienen coincidencia única en las páginas de LaLiga. La confirmación directa de orden y cierre sigue pendiente: el acceso a la página oficial de juego devolvió una restricción geográfica. No se intentó eludirla.
- J12 conserva la revisión secundaria provisional y su registro completo pendiente. No se ha creado una liquidación oficial ficticia.

## Comandos

Desde la raíz del repositorio, con Python y dependencias del proyecto:

```powershell
$env:PYTHONPATH='src'
python scripts/economic_registry.py register --observation RUTA_A_BOLETO_CONFIRMADO.json --maximum-budget 10
python scripts/economic_registry.py summary --output-dir outputs/reports/NUEVA_REVISION
python scripts/run_prospective_cycle.py --observation RUTA_A_BOLETO_CONFIRMADO.json --snapshot RUTA_A_CUOTAS_ACTUALES.json --dataset data/processed/matches_quiniela_20261014.parquet --output-dir outputs/predictions/NUEVO_CICLO
python scripts/optimize_economic_research.py --forecast outputs/predictions/registry/2026_j12/forecast.json --scenarios configs/payout_sensitivity_j12.json --budget 10 --output-dir outputs/reports/NUEVA_FRONTERA
```

Los nombres `RUTA_A_...` son marcadores; no hay un boleto futuro confirmado fabricado. Las carpetas de salida deben ser nuevas. `run_status.json` distingue bloqueos, abstención registrada, pareja registrada y finalización. Un fallo después de un registro no borra ese registro; la abstención idéntica puede reutilizarse en un nuevo intento.

El ciclo 50/50 conserva su presupuesto y protocolo originales de 5 € hasta el 1 de julio de 2027. El soporte de 10 € no cambia sus pesos, código de predicción congelado ni cohorte. La estrategia económica necesitará otro protocolo, fechas y escenarios fijados cuando se valide el modelo de premios. No se ha programado una ejecución recurrente.

## Comprobaciones

Se ejecutaron 83 pruebas focalizadas: cobros y riesgo con trece columnas, enumeración independiente de subconjuntos de signos para el optimizador, céntimos/recuperación exacta, datos desconocidos, importes inválidos, v1/v2, sellos alterados, abstenciones, selecciones públicas y fechas, bootstrap y ausencia de resultados de la misma semana en las variables. Ruff pasó para los archivos modificados/nuevos. Los registros J11/J12 y los hashes de modelos/candidato 50/50 permanecieron válidos.

## Próximo paso operativo

Confirmar el boleto y cierre de J14 mediante una captura autorizada de SELAE, actualizar resultados terminados y capturar cuotas próximas a la decisión. Después ejecutar el ciclo prospectivo. La preparación preliminar de J14 sirve para revisar el flujo de 10 €; la recomendación económica sigue siendo abstenerse por evidencia insuficiente. Antes de cualquier piloto real se deberá acordar el límite acumulado de pérdidas.
