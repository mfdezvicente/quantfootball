# Fuerzas dinámicas y calibración temporal — 02-10-2026

## Resultado de esta iteración

Se compararon tres modelos de goles dinámicos, sus mezclas con el candidato
anterior y tres opciones de calibración. Los 1.287 ajustes semanales convergieron.
La selección conserva los modelos masculinos anteriores e incorpora dinámica
en Liga F. El modelo principal de `quiniela_spain.json` sigue disponible.

| Competición | Log loss anterior | Log loss elegido | Brier elegido | Acierto elegido | Partidos |
|---|---:|---:|---:|---:|---:|
| Primera | 0,972316 | 0,972316 | 0,576058 | 53,16 % | 760 |
| Segunda | 1,044906 | 1,044906 | 0,628748 | 46,54 % | 924 |
| Liga F | 0,893975 | 0,886576 | 0,522108 | 60,00 % | 480 |

La referencia masculina es el candidato de forma ya seleccionado, no el
modelo principal sin forma. En Liga F, la mezcla elegida usa un 25 % del modelo
dinámico con precisión de transición 48 y un 75 % del modelo de goles anterior.
La calibración elegida multiplica los logaritmos de las probabilidades por
1,048507 antes de aplicar softmax, equivalente a temperatura 0,953737.

La diferencia en Liga F es −0,007399 de log loss, con intervalo descriptivo de
remuestreo por semanas [−0,012936; −0,001709]. El acierto pasa de 285 a 288
partidos de 480. Por temporada, las diferencias son −0,005412 en 2024–25
(su intervalo incluye cero) y −0,009386 en 2025–26. Los intervalos no corrigen
la búsqueda entre candidatos y no certifican una mejora futura.

## Qué aporta cada componente en Liga F

| Alternativa | Log loss 2024–26 | Brier |
|---|---:|---:|
| Candidato anterior | 0,893975 | 0,527752 |
| Anterior + calibración de temperatura | 0,894542 | 0,528022 |
| Mezcla dinámica elegida sin recalibrar | 0,886212 | 0,522024 |
| Mezcla dinámica con calibración elegida | 0,886576 | 0,522108 |

La mejora procede de la mezcla dinámica. La calibración ganó por muy poco
en validación, pero empeora ligeramente el diagnóstico posterior. Se conserva
la decisión anterior a ese diagnóstico; quitarla porque hemos visto estos
resultados sería ajustar el modelo al periodo que queremos evaluar.
La calibración con sesgos distintos para local/empate/visitante tampoco fue
seleccionada. No se fuerza una corrección de empates si no mejora la comparación.

## Modelo

`DynamicGoalModel` crea un estado ofensivo y otro defensivo por equipo y mes
con partidos observados. Se ajusta cada competición por separado. La defensa
se representa con signo de debilidad: un valor positivo aumenta los goles
esperados del rival.

Las intensidades son:

```text
log(lambda_local) = base + ventaja_local + ataque_local,t + defensa_visitante,t
log(lambda_visitante) = base + ataque_visitante,t + defensa_local,t
```

Una penalización gaussiana inicial acerca los equipos a la media de su liga.
Las transiciones penalizan `estado_actual - phi * estado_anterior`, con
`phi = 2 ** (-meses_transcurridos * 30,4375 / 730)`. La precisión de transición
se divide por el número de meses transcurridos: un parón largo permite más
cambio y acerca la media a cero. Hay regularización adicional por estado.
Se comparan precisiones 12, 48 y 192, manteniendo los demás parámetros fijos.
La semivida de ponderación de resultados es de 730 días y la ventana, 1.461.

Las fuerzas y la corrección de marcadores bajos se estiman conjuntamente,
con gradiente analítico y L-BFGS-B. La corrección utiliza
`rho(local,visitante) = kappa / ((1 + lambda_local) * (1 + lambda_visitante))`,
con `kappa` entre −0,95 y 0,95. Los cuatro ajustes 0–0/0–1/1–0/1–1 conservan
las marginales Poisson y mantienen una distribución válida para cualquier
pareja de equipos. Es una extensión acotada del tipo Dixon–Coles, **no el
Dixon–Coles original con rho constante**.

Las penalizaciones pueden interpretarse como priors gaussianos con parámetros
fijos. Se calcula una estimación penalizada de los estados; no se integra una
distribución posterior bayesiana. Las ideas de evolución temporal están
relacionadas con la [literatura de modelos dinámicos de fútbol](https://academic.oup.com/jrsssd/article/51/2/157/7120674),
pero esta implementación no pretende reproducir sus algoritmos.

## Diseño temporal

1. Cada predicción se entrena sólo con partidos anteriores al lunes de su semana.
2. Los pronósticos de 2022–23 ajustan el calibrador de cada alternativa.
3. Se eligen modelo, peso y tipo de calibración con el log loss de 2023–24.
4. Se vuelve a ajustar el calibrador elegido con pronósticos de 2022–24.
5. Se congelan sus parámetros y se calculan métricas de 2024–26.

El calibrador considera identidad, temperatura y temperatura con sesgos de clase;
usa regularización hacia identidad y límites explícitos. No utiliza particiones
aleatorias. Las métricas incluyen log loss, Brier, acierto y frecuencias por tramo
de probabilidad. Véase la [documentación de calibración de scikit-learn](https://scikit-learn.org/stable/modules/calibration.html)
para la distinción entre calibración y capacidad de discriminación.

**La evaluación es exploratoria:** las temporadas 2024–26 ya habían sido
inspeccionadas y el candidato anterior se seleccionó usando 2022–24. Por ello,
el conjunto del proceso no es una validación totalmente anidada ni una nueva
prueba final sin observar. Se usan los datasets históricos inmutables: 9.397
partidos masculinos y 1.546 femeninos. No se añaden los once partidos masculinos
nuevos al experimento; el snapshot actual sigue disponible para pronosticar.

Las tablas de probabilidades, ajustes, ranking completo, hashes de datos/código
y copia del código usado en la generación quedan en
`outputs/reports/dynamic_calibration_v1/`. Las comparaciones secundarias entre
componentes no cambian el ganador seleccionado.

## Quinielas y retorno

`configs/quiniela_dynamic_candidate.json` activa la mezcla sólo en Liga F.
El generador aplica primero el candidato anterior completo, después la mezcla
dinámica y finalmente la calibración. Cada remuestreo semanal reajusta también
el modelo dinámico; los parámetros del calibrador permanecen fijos.

Los optimizadores reciben estas nuevas probabilidades. Se conservan las
alternativas exactas de cobertura de 14 y de al menos 10 en sistemas completos,
además de las heurísticas conservadoras. No se asignan dobles por varianza sola.
El Pleno sigue usando el modelo de goles anterior: no se ha elegido una mezcla
dinámica por su rendimiento específico en el Pleno oficial.

**No se ha calculado un nuevo ROI del candidato dinámico.** Los 61 concursos
del visor siguen conservando las probabilidades y liquidaciones originales.
Sus retornos negativos no se atribuyen al nuevo candidato. No hay cuotas reales
ni porcentajes apostados nuevos: siguen haciendo falta datos autorizados y con
fechas verificables para comparar con el mercado y estimar premios esperados.

El protocolo `outputs/reports/dynamic_calibration_v1/prospective_protocol.json`
fija una evaluación nueva desde 03-10-2026 hasta 30-06-2027, con configuración,
criterios, estrategia y presupuesto máximo de 5 €. No registra un concurso.
Se deben verificar los quince partidos oficiales y la hora de cierre, actualizar
los resultados que falten y registrar ambos pronósticos antes del cierre y del
primer partido. El historial puede crecer con resultados anteriores, manteniendo
congelados hiperparámetros y calibración. No existe todavía un boleto completo
futuro registrado para ROI ni un sello temporal externo. Posteriormente se
guardó un par de catorce probabilidades de clubes para la jornada 11, en un
estudio separado: su Pleno de selecciones está fuera del alcance acordado.
Véase [THE_ODDS_API.md](THE_ODDS_API.md).

## Visores y reproducción

- `outputs/reports/dynamic_calibration_v1/dashboard.html`: comparación probabilística,
  gráfica de calibración por liga y resultado, componentes, temporadas y los
  concursos históricos originales. Sus retornos pertenecen al modelo original.
- `outputs/reports/mixed_dynamic_demo_v2/dashboard.html`: ejemplo con partidos reales
  de septiembre de 2026, incluyendo cuatro de Liga F; **no es un concurso oficial**.
  Permite comparar presupuestos de 1,50 a 5 € y las cinco estrategias disponibles.

```powershell
python scripts/evaluate_dynamic.py --output-dir outputs/reports/dynamic_new
python scripts/plan_spain.py --dataset data/processed/matches_quiniela_current.parquet --config configs/quiniela_dynamic_candidate.json --fixtures examples/mixed_competitions_demo.json --pleno examples/mixed_competitions_demo_pleno.json --cutoff 2026-09-18 --draws 16 --example --evaluation outputs/reports/dynamic_calibration_v1/dashboard_evaluation.json --output-dir outputs/reports/dynamic_demo_new
```

El primer comando produce probabilidades, ajustes, métricas y configuración de
investigación; requiere los informes anteriores en `outputs/reports`. El segundo
genera un ejemplo con el presupuesto de 5 €; los seis presupuestos del visor
publicado se calculan sobre ese mismo pronóstico congelado. Nunca reutilizar
un directorio de salida de una generación anterior.

Se ejecutaron la evaluación de modelos, el generador del ejemplo, revisión
estática de Python, lint y comprobación de sintaxis JavaScript. No se añadieron
ni ejecutaron pruebas unitarias. El HTML no se inspeccionó visualmente en un
navegador en esta iteración.
