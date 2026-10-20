# Auditoría histórica de premios — 19 de octubre de 2026

Se auditan todos los domingos del 4 de agosto de 2024 al 7 de junio de 2026: 97 fechas, 89 tablas completas de seis categorías y ocho fechas sin tabla en el archivo. Esto no prueba que existiera concurso en cada una de esas ocho fechas. La ventana no incluye los concursos de entre semana. No se exige que los partidos sean elegibles para el predictor para revisar su contabilidad.

Las ocho fechas sin tabla son 11/08/2024, 03/11/2024, 29/12/2024, 02/03/2025, 15/06/2025, 22/06/2025, 07/09/2025 y 28/12/2025. Se conservan en el informe, sin convertirlas en liquidaciones de cero euros.

## Datos incorporados y procedencia

Se añaden cuatro observaciones numéricas de notas oficiales: 04/08/2024, 13/04/2025, 24/05/2026 y 07/06/2026. Incluyen recaudación, acertantes y premio unitario de las seis categorías. Son ejemplos elegidos para contrastar ramas de reparto, no una muestra representativa del ROI.

Las notas se observaron mediante extracción de texto del buscador. Las descargas directas devolvieron HTTP 403 y no se reintentaron por otras rutas. No disponemos de los PDF completos archivados. Cada observación conserva URL, momento de registro, método de extracción, fecha del documento y ausencia de hora de publicación verificada. `source_access/` guarda los diagnósticos de descarga. Los extractos antiguos tienen hashes, pero no un momento de captura históricamente verificable.

## Reconstrucción y límites

El módulo `quantfootball.quiniela.prize_audit` calcula fondos a partir de recaudación y acertantes finales. Soporta reparto ordinario, transferencias por ausencia de acertantes y supresión del premio de diez inferior al mínimo. Bloquea igualaciones y redistribuciones superiores pendientes de implementación. El Pleno requiere un bote de entrada conocido; no se ajusta ese bote al premio que después se pretende validar.

Los 17 premios ordinarios con acertantes de los cuatro ejemplos coinciden al céntimo bajo dos hipótesis de redondeo: fondo exacto o fondo previamente redondeado. Esta muestra no permite identificar la convención oficial de redondeo. La coincidencia no valida todas las ramas excepcionales del reglamento.

En el ejemplo del 07/06/2026, el Pleno publicado es un suplemento a los catorce aciertos. El experimento sintético con bote previo cero comprueba esa suma, pero el registro observado mantiene el bote desconocido. Los premios de diez con acertantes y valor cero se distinguen de ausencia de acertantes o de datos.

Normas consultadas: https://www.loteriasyapuestas.es/f/loterias/documentos/normativa/Normativa%20de%20los%20juegos/Normas_de_la_Quiniela_y_Elige8_Octubre_2019.pdf (normas 6 a 8). El motor es de investigación y no certifica liquidaciones oficiales.

## Reproducción de cobros históricos

Se reproducen 305 liquidaciones: 61 jornadas por cinco estrategias, contrastando las tablas originales y recalculando costes, cobros y aciertos con columnas y signos congelados. Los signos se toman del experimento anterior: no se han verificado de nuevo contra una nueva fuente de resultados. No hay diferencias.

La selección de columnas individuales conserva coste 274,50 €, cobro bruto 120,08 €, pérdida 154,42 € y ROI histórico bruto −56,26 %. Es un experimento retrospectivo previo, sin compras reales, impuestos ni dilución contrafactual de premios. No es el ROI de la nueva cohorte 50/50.

## Reproducir la auditoría

Desde la raíz del proyecto, usando un directorio de salida nuevo:

```
python scripts/audit_prize_economics.py --observations outputs/reports/prize_economics_20261019/observations.json --output-dir outputs/reports/prize_economics_replica
```

Los datos observados y el JSON completo permiten repetir el análisis sin red. Los archivos históricos, modelos y registros prospectivos anteriores se conservan.

## Qué falta para estimar premios futuros

Todavía no hay observaciones económicas verificadas anteriores al cierre en esta auditoría. Se necesitan más recaudaciones y fondos de bote efectivamente asignados, confirmar redondeo e igualaciones, auditar el calendario completo de concursos y recoger datos de participación antes del cierre. Con ello se podrá desarrollar una previsión de acertantes y premios que después se evalúe en jornadas nuevas.

La recaudación y los acertantes finales solo permiten reconstrucción histórica. No deben entrar como variables en una predicción anterior al cierre. El modelo de participación conjunta sigue pendiente y ninguna reconstrucción de este informe habilita recomendaciones económicas.
