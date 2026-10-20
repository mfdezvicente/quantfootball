# Primera, Segunda e incertidumbre — 25-09-2026

## Resultado de esta iteración

El nuevo flujo es `scripts/plan_spain.py`. El anterior `plan_quiniela.py` se conserva
para sus experimentos de una sola división y rechaza mezclar ligas.

- **9.397 resultados**: 4.249 de Primera y 5.148 de Segunda.
- **22 temporadas completas**: 2015–16 a 2025–26 en ambas divisiones.
- 2026–27 parcial: 69 partidos de Primera y 66 de Segunda, último resultado
  disponible el 20-09-2026. Esto no acredita estar al día con todos los encuentros.
- Recuperados los diez resultados ausentes de Primera 2024–25, tres temporadas
  de Segunda ausentes en el JSON y los tramos incompletos de Segunda 2024–26.
- Nombres canónicos explícitos, filiales separados, control de marcadores,
  duplicados, temporadas cerradas y huellas de los archivos de origen.
- Cero conflictos de marcador o fecha entre las fuentes coincidentes del snapshot.

Fuentes: snapshots de OpenFootball fijados por commit y páginas públicas de
[resultados de LaLiga](https://www.laliga.com/laliga-hypermotion/resultados/2025-26/jornada-42).
El origen queda registrado por partido. La licencia de OpenFootball no se extiende
a los datos de LaLiga o SELAE; la mezcla no se etiqueta como un dataset íntegramente CC0.

## Evaluación del modelo

Entrenamiento anterior al lunes de cada semana; sin actualizar entre sus partidos.
Selección de parámetros usando únicamente 2022–24. Diagnóstico posterior 2024–26.
Estas temporadas ya se han inspeccionado: **no constituyen una nueva prueba ciega**.
`selected_before` expresa el límite de resultados usados para seleccionar parámetros;
la fecha real de ejecución se guarda aparte. Los datos históricos contienen revisiones
actuales de las fuentes, sin reconstruir su disponibilidad original.

| División / modelo | Partidos | Log loss ↓ | Brier ↓ | Acierto |
|---|---:|---:|---:|---:|
| Primera / frecuencias | 760 | 1,0600 | 0,6397 | 46,71 % |
| Primera / Elo | 760 | 0,9814 | 0,5815 | 52,89 % |
| Primera / seleccionado | 760 | **0,9753** | **0,5779** | 53,29 % |
| Segunda / frecuencias | 924 | 1,0714 | 0,6470 | 45,56 % |
| Segunda / Elo | 924 | 1,0505 | 0,6324 | **46,86 %** |
| Segunda / seleccionado | 924 | **1,0471** | **0,6303** | 46,65 % |

Primera selecciona 50 % Elo + 50 % Dixon–Coles; Segunda selecciona Dixon–Coles.
Ambas: semivida 365 días, regularización 10, ventana 1.461 días, temperatura 0,9.
El ajuste de Dixon–Coles sigue siendo en dos etapas, no estimación conjunta.
Se optimiza log loss, por eso el seleccionado no necesariamente acierta más signos.

La diferencia de log loss frente a Elo tiene intervalo exploratorio del 95 %
[-0,0105; -0,0017] en Primera y [-0,0130; 0,0064] en Segunda.
**La mejora de Segunda no está establecida con claridad estadística.**
El informe incluye calibración por clases, resultados por temporada y casos sin historial.

## Dobles, triples e incertidumbre

Se separan dos conceptos:

1. **Equilibrio del partido**: entropía de las probabilidades 1/X/2.
2. **Inestabilidad del estimador**: se dan pesos aleatorios a semanas de entrenamiento
   y se vuelven a ajustar Elo y el modelo de goles. Se muestran dispersión,
   percentiles 5–95 y estabilidad del favorito. Los parámetros seleccionados quedan fijos.

Esto mide sensibilidad condicional a estos datos y modelos; no son intervalos
de confianza calibrados ni incorporan todas las fuentes de error. El diagnóstico
económico usa 32 remuestreos; la generación nueva usa 64 por defecto.

Cuatro alternativas bajo el mismo máximo de 5 €:

- Sistema completo óptimo para las probabilidades centrales: fijos, dobles y triples.
- Columnas individuales óptimas para esas probabilidades.
- Sistema conservador: maximiza el percentil 10 entre sistemas candidatos de los remuestreos.
- Columnas conservadoras: selección incremental entre columnas candidatas.

Las dos primeras son exactas bajo independencia de los resultados. Las conservadoras
son heurísticas: no se afirma optimalidad global ni superioridad real.
El objetivo es P(acertar los primeros 14 en alguna columna), no el valor monetario
esperado ni la probabilidad de cobrar cualquier categoría. Cubrir un partido con un
triple no garantiza acertar el boleto. 5 € permiten seis columnas a 0,75 €: 4,50 €.

## Primer retorno histórico calculado

Ventana declarada: ocho domingos consecutivos del 06-04-2025 al 25-05-2025.
Siete concursos se emparejan íntegramente con el dataset. Se excluye el 27-04 por
partidos ingleses; no se descarta ninguna jornada por su rentabilidad.
Los equipos y marcadores se contrastan con las tablas oficiales de SELAE.
Los premios no participan en el ajuste o selección de estrategias.

| Estrategia | Coste | Premios brutos | Neto | ROI observado |
|---|---:|---:|---:|---:|
| Sistema completo | 31,50 € | 4,95 € | −26,55 € | −84,29 % |
| Columnas individuales | 31,50 € | 4,95 € | −26,55 € | −84,29 % |
| Sistema conservador | 31,50 € | 2,31 € | −29,19 € | −92,67 % |
| Columnas conservadoras | 31,50 € | 2,31 € | −29,19 € | −92,67 % |

**No se ha demostrado ROI esperado positivo.** Son siete jornadas y el ROI es
negativo; la muestra no permite estimar la rentabilidad de largo plazo. Los
remuestreos por concurso no pueden reconstruir premios raros nunca observados.
Se suman premios de 14 y Pleno cuando proceda; un premio desconocido/BOTE no se
convierte en cero. Si una columna ganadora requiere un premio no publicado, se
rechaza calcular su retorno. Los premios brutos publicados no incluyen impuestos
ni la modificación del reparto por añadir nuestras apuestas.

Ejemplo de fuente: [resultados SELAE del 25-05-2025](https://www.loteriasyapuestas.es/es/la-quiniela/resultados/la-quiniela-resultados-del-25-de-mayo-de-2025)
y [escrutinio oficial](https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Notas%20de%20prensa/NOTA_DE_PRENSA_LA_QUINIELA_25_5_25.pdf).
Los extractos estadísticos y sus huellas quedan guardados. La descarga directa de
SELAE devolvió 403; los extractos proceden de sus páginas públicas consultables
mediante búsqueda web. No hay un recolector automático de concursos completo.

## Usar el visor y generar nuevas selecciones

Abrir `outputs/reports/official_v3/dashboard.html` en un navegador local.
Permite cambiar jornada, presupuesto y estrategia, consultar intervalos, ver las
columnas exactas y exportar JSON. **Su ejemplo es histórico, no una apuesta actual.**
La lógica del visor se comprueba con Node; su inspección visual automática quedó
bloqueada por la política de acceso a archivos locales del navegador integrado.

Desde el repositorio y con Python 3.12/3.13 y las dependencias instaladas:

```powershell
python scripts/plan_spain.py --fixtures examples/coupon_2025-05-25.json --pleno examples/pleno_2025-05-25.json --cutoff 2025-05-23 --budget 5 --output-dir outputs/predictions/demo_spain
```

Para un concurso futuro, cambiar los 14 partidos y su corte. El JSON requiere
`position`, `date`, `home_team`, `away_team`, `competition_code` (`es.1` o `es.2`).
El Pleno se suministra aparte. Los equipos sin historial de su división se rechazan.
El programa no valida la composición ni el cierre de un concurso futuro con SELAE:
hay que aportar los partidos oficiales. Los boletos con otras ligas, Copa o fútbol
femenino necesitan modelos y datos de esas competiciones.

Cada ejecución usa un directorio nuevo e incluye probabilidades, remuestreos,
configuración, fecha real, hashes de datos/código y HTML. No sobrescribe predicciones.

## Reproducir

```powershell
python scripts/fetch_spanish_snapshot.py
python scripts/fetch_laliga_results.py
python scripts/build_spanish_dataset.py
python scripts/evaluate_spain.py --output-dir outputs/reports/nueva_evaluacion
python scripts/backtest_official.py --config configs/quiniela_spain.json --output-dir outputs/reports/nuevo_backtest
python scripts/render_dashboard.py --report outputs/reports/nuevo_backtest/roi.json --evaluation outputs/reports/nueva_evaluacion/evaluation.json --audit data/processed/matches_spain.audit.json --output outputs/reports/nuevo_backtest/dashboard.html
python -m pytest -q
node tests/dashboard_check.cjs outputs/reports/nuevo_backtest/dashboard.html
```

El recolector de LaLiga reconstruye las jornadas utilizadas en este snapshot;
no es todavía un servicio continuo de actualización. Los extractos oficiales y
los snapshots locales quedan fuera de Git conforme al `.gitignore` existente.
El manifiesto fijado y un pequeño ejemplo de prueba sí se versionan. Para repetir
el backtest desde otro clon hay que copiar/importar sus extractos oficiales.

## Trabajo que sigue siendo necesario

Actualización posterior de esta iteración: [archivo ampliado y transferencia entre divisiones](RESEARCH_EXPANSION.md).
El visor ampliado está en `outputs/reports/official_expanded_v1/dashboard.html`.
Conservamos las cifras anteriores para mantener la trazabilidad de la primera evaluación.

1. Ampliar el archivo de concursos y escrutinios a varias temporadas completas,
   registrando también los excluidos y las fechas de publicación/cierre.
2. Registrar pronósticos futuros antes del cierre para obtener una prueba realmente nueva.
3. Tratar ascensos/descensos con transferencia de fuerza entre divisiones y evaluar
   su mejora; actualmente se usa el historial de la división y se marca si es escaso.
4. Contrastar con probabilidades de mercado disponibles antes del cierre, con una
   fuente autorizada para este uso, y estudiar los porcentajes apostados públicos.
5. Optimizar retorno esperado solamente cuando ese archivo permita estimar el reparto.
   Los escrutinios bastan para ROI realizado; los porcentajes ayudan a valorar premios futuros.

La información de alineaciones/lesiones, estados administrativos de partidos y la
dependencia entre resultados tampoco está modelada. Añadirla exige datos temporales
fiables y demostrar mejora frente a los modelos actuales.
