# Archivo ampliado y transferencia entre divisiones

Actualización: 25 de septiembre de 2026. Esta iteración mantiene el presupuesto
máximo de 5 € y la selección por cobertura. No optimiza las estrategias usando
los premios observados.

## Archivo de concursos y rentabilidad

Se han revisado **los 97 domingos entre 04-08-2024 y 07-06-2026**. Hay **61 concursos
liquidables** con resultados de Primera/Segunda y sus seis categorías de premios
oficiales. Los otros **36 quedan registrados con su motivo de exclusión**.
No son dos temporadas completas de concursos: faltan los de otros días y los
que incluyen otras competiciones, partidos aplazados o resultados administrativos.

| Estrategia | Coste (€) | Premios (€) | Neto (€) | ROI observado |
|---|---:|---:|---:|---:|
| Dobles/triples por cobertura | 274,50 | 117,10 | -157,40 | -57,34 % |
| Columnas individuales por cobertura | 274,50 | 120,08 | -154,42 | -56,26 % |
| Dobles/triples conservadores | 274,50 | 98,92 | -175,58 | -63,96 % |
| Columnas individuales conservadoras | 274,50 | 98,08 | -176,42 | -64,27 % |

Se liquidan 61 concursos a 4,50 € por concurso (seis columnas).
En total hay 4 partidos de los primeros catorce con marca de falta de historial reciente en su división.

Los importes son una simulación retrospectiva de premios brutos publicados;
no incluyen impuestos ni el cambio del reparto que producirían nuestras propias
apuestas. Los intervalos de remuestreo de concursos tampoco pueden cuantificar
premios extraordinarios que nunca aparecen en la muestra. **Este análisis no
demuestra un ROI esperado positivo.** La selección por disponibilidad y por
tipo de liquidación puede introducir sesgo; los resultados son condicionales a
estos concursos, no el retorno de una política que apostase todos los domingos.

Cada jornada conserva el corte común anterior a todos sus partidos, las
probabilidades, 32 remuestreos de semanas, las cuatro estrategias y sus columnas,
fuentes, hashes y premios. El modelo principal se mantiene fijado por la
validación 2022–24. El periodo 2024–26 ya había sido inspeccionado: es diagnóstico
retrospectivo, no una prueba final intacta.

En este estudio se admite explícitamente un prior neutral para equipos sin
historial reciente en su división. Se identifican con `cold_start`; es una
limitación, especialmente al principio de temporada. La generación habitual
conserva el rechazo de esos equipos salvo activación expresa de una política.

Archivos:

- `outputs/reports/official_expanded_v1/dashboard.html`: visor de selecciones,
  presupuestos, probabilidades y retornos agregados y por temporada.
- `outputs/reports/official_expanded_v1/roi.json`: resultados completos.
- `outputs/reports/official_expanded_v1/archive_audit.json`: calendario completo,
  exclusiones, excepciones administrativas y hashes de los extractos.
- `data/raw/official_expanded`: extractos estadísticos públicos y registro de
  recuperación. Los prefijos `QF:` identifican campos normalizados de resultados
  indexados; no pretenden ser números de línea del documento original.

Los extractos de estadísticas se recuperaron mediante consultas web públicas.
Algunos PDF tienen fechas o rutas irregulares, conservadas en los extractos.
No se ha implementado todavía una descarga continua fiable del archivo completo.
Como los datos y los informes se ignoran en Git, hay que copiarlos para reproducir
este estudio desde un clon nuevo; el código no los inventa cuando faltan.

## Correcciones de datos y liquidación

Se amplió la equivalencia explícita de nombres de SELAE (Ceuta, Andorra, Racing,
Zaragoza y Valladolid). El lector ahora **rechaza importes contradictorios**
para una misma categoría, en vez de sustituirlos silenciosamente. Los premios
desconocidos y los botes siguen sin convertirse en cero.

El Valencia–Oviedo del concurso de 28-09-2025 se resolvió por sorteo para la
Quiniela. El resultado deportivo posterior fue 1–2; el signo oficial adjudicado
fue 1. El caso queda documentado en `configs/settlement_exceptions.json` y se
excluye de esta evaluación. El dato deportivo del entrenamiento se conserva.
Fuente: [aviso oficial de SELAE](https://www.loteriasyapuestas.es/f/loterias/web_corporativa/Comunicacion/Avisos_de_interes/AVISO%20APLAZAMIENTO%20VALENCIA-R.%20OVIEDO%20LA%20QUINIELA.pdf).
Modelar estas situaciones exige conocer las reglas y probabilidades del sorteo
antes del cierre; excluirlas retrospectivamente no resuelve ese problema.

## Modelo experimental para ascensos y descensos

Se añadió un Elo común a las dos divisiones. Conserva la fuerza previa cuando un
equipo cambia de categoría, aplica una diferencia de nivel entre ligas y reduce
la desviación individual al comenzar otra temporada. El modelo de goles sigue
siendo independiente por división: todavía no transfiere parámetros de ataque
y defensa entre ligas.

Se compararon 16 configuraciones y cuatro pesos de mezcla, escogidos únicamente
por log loss en 2022–24, incluyendo peso cero como opción. En Primera se seleccionó
**peso cero**, por lo que no cambia su pronóstico. En Segunda se seleccionó
**25 % de Elo transferido** y 75 % del modelo anterior, diferencia de nivel de
300 puntos, conservación de desviación de 0,75 y penalización inicial de 80 puntos
para equipos nuevos en el archivo.

| División | Partidos diagnósticos | Log loss anterior | Log loss candidato |
|---|---:|---:|---:|
| Primera | 760 | 0,9753 | 0,9753 |
| Segunda | 924 | 1,0471 | 1,0452 |

En Segunda, la diferencia es −0,00183, con intervalo exploratorio del 95 %
**[−0,00469; +0,00108]** mediante remuestreo de semanas. La media mejora ligeramente,
pero el intervalo incluye cero. No hay evidencia suficiente para promoverlo
como modelo principal; tampoco se ha calculado un ROI separado para elegirlo.

La configuración optativa está en `configs/quiniela_transfer_candidate.json` y
el informe en `outputs/reports/transfer_v1/evaluation.json`. La configuración
por defecto sigue siendo `configs/quiniela_spain.json`. El candidato refita
también el Elo transferido en cada remuestreo; no considera fija esa parte de
la incertidumbre. Puede usar el historial de otra división para equipos que
cambian de categoría, conservando la marca de historial de goles insuficiente.

## Reproducir y usar

Desde la raíz del repositorio, con sus dependencias instaladas y el archivo de
datos local disponible. Cada evaluación debe usar un directorio de salida nuevo:

```powershell
python scripts/audit_official_archive.py --output outputs/reports/auditoria_nueva.json
python scripts/evaluate_transfer.py --baseline outputs/reports/spain_v5 --output-dir outputs/reports/transfer_nuevo
python scripts/backtest_official.py --config configs/quiniela_spain.json --raw-dir data/raw/official_expanded --start 2024-08-04 --end 2026-06-07 --allow-cold-start --output-dir outputs/reports/concursos_nuevo
python scripts/render_dashboard.py --report outputs/reports/concursos_nuevo/roi.json --evaluation outputs/reports/spain_v5/evaluation.json --audit data/processed/matches_spain.audit.json --output outputs/reports/concursos_nuevo/dashboard.html
```

Para probar el candidato con el ejemplo histórico:

```powershell
python scripts/plan_spain.py --fixtures examples/coupon_2025-05-25.json --pleno examples/pleno_2025-05-25.json --config configs/quiniela_transfer_candidate.json --cutoff 2025-05-23 --budget 5 --output-dir outputs/predictions/ejemplo_transfer
```

El visor muestra las columnas reales y el desarrollo de dobles/triples. Un doble
o triple aumenta la cobertura y el coste; no asegura el premio del boleto. Las
bandas del modelo expresan sensibilidad al historial, no garantías.

## Siguiente evidencia necesaria

1. Guardar pronósticos y boletos oficiales **antes de su cierre**, para evaluar
   resultados realmente nuevos sin ajustar después la configuración.
2. Ampliar el registro de concursos, cierre y casos administrativos con datos
   disponibles en cada momento. Incorporar otras competiciones requiere modelos
   específicos y su validación.
3. Incorporar probabilidades de mercado y porcentajes apostados con fecha de
   captura anterior al cierre. Los premios históricos permiten medir retorno
   realizado; para optimizar retorno esperado hace falta estimar el reparto.
4. Evaluar modelos conjuntos de ataque/defensa y transferencia de categoría,
   calibración por división y estabilidad en temporadas sucesivas, evitando
   seleccionar complejidad por el mejor resultado retrospectivo.
