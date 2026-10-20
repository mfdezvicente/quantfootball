# Quiniela V0: cobertura con presupuesto de 5 EUR

Objetivo acordado: maximizar la probabilidad estimada de al menos una columna
con 14 aciertos, con un presupuesto configurable de referencia de 5 EUR.
La rentabilidad se incorporara cuando existan datos fiables de apuestas y premios.

## Alcance entregado

- Optimizador exacto de sistemas completos de simples, dobles y triples.
- Optimizador exacto de columnas individuales distintas, sin restriccion cartesiana.
- Precio configurable en la API monetaria; el plan usa 0,75 EUR por columna.
  Con 5 EUR, como maximo seis columnas (4,50 EUR).
- Pronosticos del ensemble Elo + Dixon-Coles congelados antes de la fecha de sellado,
  Elo como alternativa o probabilidades externas. [Modelo y evaluacion](ADVANCED_MODEL.md).
- Pronostico opcional del Pleno al 15 con las 16 categorias de goles.
- Informe JSON con columnas, probabilidades, coste, saldo y trazabilidad del codigo y datos.
- Los informes existentes no se sobrescriben.

La optimalidad es matematica respecto a las probabilidades introducidas y supone
independencia entre partidos. No demuestra que Elo este calibrado ni garantiza aciertos.
La cobertura es P(al menos una columna con los 14 signos correctos), no P(cobrar).
Sin `--pleno`, queda por elegir el Pleno al 15. No incluye
Elige8, premios, ROI ni compra de apuestas. Las columnas individuales no deben
convertirse en una union de signos y jugarla como sistema completo: costaria mas.

## Instalacion y demostracion

Desde la raiz del repositorio, con Python 3.12 o 3.13:

```powershell
python -m pip install -e ".[dev]"
python scripts/plan_quiniela.py --probabilities examples/quiniela_demo.json --budget 5 --output outputs/predictions/demo_quiniela.json
```

El ejemplo es totalmente sintetico: equipos y probabilidades inventados para
demostrar el funcionamiento. No representa un concurso real ni una recomendacion.

Para obtener probabilidades del ensemble avanzado (o usar `--model elo`):

```powershell
python scripts/plan_quiniela.py --fixtures mi_jornada.json --cutoff 2026-09-24 --budget 5 --output outputs/predictions/mi_jornada.json
```

`mi_jornada.json` es una lista de exactamente 14 objetos, en el orden oficial:

```json
[
  {"position": 1, "date": "2026-09-26", "home_team": "Equipo local", "away_team": "Equipo visitante"}
]
```

El fragmento muestra solo la estructura de una fila; hay que incluir las 14.
Con `--probabilities`, cada objeto necesita tambien `p_home`, `p_draw`, `p_away`
en orden 1/X/2, sumando uno. Estas probabilidades se consideran externas; su
disponibilidad antes del cierre y su calibracion no quedan verificadas por el programa.

El modelo rechaza equipos sin historial. Las fechas de partidos no pueden preceder
la fecha de sellado. Como el dataset no registra la hora de disponibilidad de los
resultados, se excluye conservadoramente todo el dia del corte. No se actualiza Elo
entre los 14 pronosticos. El fichero historico debe corresponder a la informacion
conocida en ese momento; sus posibles correcciones posteriores siguen siendo una
limitacion de los backtests.

## Actualización del 25-09-2026

El flujo de Primera y Segunda, sus datos completos, remuestreo de incertidumbre,
visor y primer ROI histórico se documentan en [SPAIN_MODEL.md](SPAIN_MODEL.md).
Usar `scripts/plan_spain.py` para boletos mixtos. Lo siguiente describe el estado anterior.

## Estado histórico de los datos revisado el 24-09-2026

La copia local contiene 4.170 resultados de Primera Division de 2015-16 a 2025-26.
El Parquet tiene 370 resultados de 2024-25; la cache JSON tiene 380 encuentros,
pero los diez de la jornada 38 tienen `score: {}`. El pipeline los excluye
correctamente como no completados. Hay que recuperar sus resultados en la fuente.
No se encontraron historicos oficiales de boletos ni datos de Segunda.
Por ello no se presenta un backtest de rentabilidad ni una quiniela real completa.

## Siguientes entregas

1. Auditar los 10 encuentros de 2024-25 y recopilar resultados de Segunda.
2. Incorporar concursos oficiales, orden de partidos, cierre y Pleno al 15.
3. Backtest por concurso con el mismo corte temporal para todas las predicciones.
4. Extender la evaluacion semanal ya realizada del ensemble a cobertura de boletos oficiales.
5. Archivo de porcentajes apostados y escrutinios para estudiar retorno esperado.

## Referencias

- [SELAE: como jugar](https://www.loteriasyapuestas.es/es/centro-de-ayuda/como-se-juega/como-jugar-a-la-quiniela)
- [Normativa enlazada por SELAE](https://www.loteriasyapuestas.es/f/loterias/documentos/normativa/Normativa%20de%20los%20juegos/Normas_de_la_Quiniela_y_Elige8_Octubre_2019.pdf)

Consultadas el 24-09-2026. La tarifa del plan no incluye Elige8; el Pleno al 15
requiere un pronostico adicional por columna, disponible mediante `--pleno`.
