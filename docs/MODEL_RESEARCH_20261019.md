# Diagnóstico y experimentos del predictor — 19 de octubre de 2026

Se han completado dos trabajos: diagnóstico del modelo actual y experimentos de nuevas variables con el mismo clasificador, peso y calendario de entrenamiento.

## Diagnóstico disponible

Se revisan 760 partidos de Primera, 924 de Segunda y 480 de Liga F de 2024–2026. Los periodos ya se habían observado en investigaciones previas. No constituyen confirmación nueva e independiente.

El promedio previsto de empates es 24,26 % frente a 25,00 % observado en Primera; 27,53 % frente a 26,52 % en Segunda; 21,55 % frente a 21,25 % en Liga F. El gráfico por rangos muestra desajustes que se ocultan al mirar solo promedios. Estas diferencias no justifican una subida general del empate.

Los favoritos ≥70 % de Primera acertaron 85 de 98 partidos (86,73 %). El segmento 50–60 % tiene 164 casos y acierta 48,17 %, con confianza media 54,63 %. En Segunda solo existen tres casos ≥70 %, insuficientes para una conclusión sobre favoritos fuertes.

Hay 216 partidos de Primera con algún equipo que jugaba en Segunda la temporada anterior. Su log loss es 0,91236, frente a 0,97232 global: no aparecen como el peor segmento agregado. Los clubes sin temporada previa en las ligas cubiertas sí requieren seguimiento, pero esa etiqueta puede reflejar una ausencia de historial y no confirma por sí misma un ascenso.

La comparación de mercado utiliza los mismos 24 encuentros y el primer estudio sellado de cada partido: nueve de Primera y quince de Segunda. El mercado obtiene menor log loss en ambos grupos. Se excluye el partido abandonado y se mantiene visible la falta de cuotas femeninas. La mezcla 50/50 calculada aquí es retrospectiva y queda fuera de su cohorte prospectiva.

## Experimentos controlados

Se mantienen boosting de siete hojas y regularización 30 para Primera, regresión logística C=1 para Segunda, entrenamiento conjunto con ambas ligas, ventana móvil de seis años y peso final del clasificador del 25 %. Se conservan las versiones originales de variables base. Se comprueba la reproducción de probabilidades originales en tres cortes por división: diferencia máxima inferior a 10⁻⁹.

Cinco grupos de variables se prueban por separado: puntos frente a los esperados según el rival, estados dinámicos de ataque/defensa, tiempo desde el último resultado conocido, congestión de liga en 7/14/28 días y continuidad de división. Los estados dinámicos nuevos son variables auxiliares con constantes fijas, distintos del modelo dinámico completo de goles ya existente.

Se completan 400 ajustes mensuales. Todos usan etiquetas anteriores a su corte de entrenamiento; las variables usan resultados anteriores al lunes del partido. El calendario es el archivado al final y no prueba que esos horarios se conocieran históricamente. Descanso y congestión solo incluyen liga, sin Copa o Europa.

La selección usa log loss de 2022–2024. El diagnóstico posterior usa 2024–2026, con las mismas identidades de partido para todas las variantes. Los intervalos por semanas son exploratorios y no corrigen la selección repetida de modelos ni toda la dependencia temporal.

| División | Modelo actual | Variante elegida en selección | Log loss diagnóstico de la variante | Diferencia frente al actual | Intervalo exploratorio 95 % |
|---|---:|---|---:|---:|---|
| Primera | 0,972316 | Ataque/defensa dinámicos | 0,971957 | −0,000359 | [−0,001883; +0,001208] |
| Segunda | 1,044906 | Descanso | 1,044759 | −0,000147 | [−0,000855; +0,000755] |

Ambas son candidatas de investigación, con diferencias pequeñas e intervalos que incluyen cero. Congestión tiene el mejor diagnóstico puntual de Segunda (1,044491), pero no ganó en el periodo de selección; no se elige retrospectivamente por ese resultado. Continuidad de división empeora en Segunda (+0,000824 de log loss en este experimento).

## Componente dinámico completo de goles

Se comprueban adicionalmente pesos 0, 0,25 y 0,50 del modelo dinámico existente, con precisión 48 y calibración final fija. Se reutilizan predicciones semanales archivadas, verificando que todos los ajustes del componente convergieron y usaron resultados anteriores al corte.

En Liga F, quitar el componente dinámico empeora el diagnóstico; aumentarlo de 0,25 a 0,50 mejora puntualmente de 0,886576 a 0,881874, con intervalo de diferencia que incluye cero. Este diagnóstico no selecciona un nuevo peso. En Segunda, el peso 0,25 mejora ligeramente; Primera no mejora en esta comparación.

## Resultado operativo y próximos experimentos

El modelo actual sigue siendo la referencia. No se modifica ningún peso, modelo de producción o protocolo prospectivo. Los siguientes candidatos a estudiar son las variables dinámicas de Primera y descanso de Segunda; necesitan una definición y evaluación prospectiva propias antes de sustituir la referencia.

Conviene priorizar fuentes históricas autorizadas de calendario de Copa/Europa y, si su cobertura es fiable, información de goles esperados y alineaciones. El diagnóstico por rangos también orienta una futura prueba de calibración condicionada al equilibrio y al nivel esperado de goles. Estas propuestas necesitan experimentos separados; no se ajusta ahora el modelo usando sus errores recientes.

## Reproducción

Con el entorno del proyecto y una carpeta de salida nueva:

```
python scripts/evaluate_ablation_research.py --output-dir outputs/reports/ablation_replica
```

El experimento conserva protocolo, hashes de datasets, predicciones de cada variante y copia del código exacto usado. El generador del panel está incluido en el informe. La versión inicial del script usada en esta ejecución se conserva allí; el comando instalado añade automáticamente esa conservación de fuentes a ejecuciones nuevas.

Las verificaciones comprueban 20.208 predicciones emparejadas (incluyen selección y diagnóstico para seis variantes de las dos ligas). Las pruebas de propiedades temporales, alineación y formulario suman 14 casos superados; Ruff también pasa. No se ha estimado ni demostrado una mejora del ROI.
