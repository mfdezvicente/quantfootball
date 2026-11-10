# J20 · experimento retrospectivo

La ejecución reutiliza la configuración del comparador de la J18, con 64 muestras de parámetros y un límite de 5 €. La selección principal usa seis columnas individuales. El corte exclusivo es el 7 de noviembre de 2026 a las 00:00 en Madrid. Los resultados del boleto se usan en la liquidación y evaluación deportiva después de calcular el pronóstico.

Las capturas de calendario e histórico se recogieron después de la jornada. El corte precede al primer partido y a los horarios de cierre publicados por terceros. La hora oficial exacta de cierre queda sin verificar. La casilla 14, aplazada y resuelta por sorteo, se liquida con el signo oficial. La probabilidad mostrada para ese cruce corresponde al partido hipotético.

- [Panel y liquidación](dashboard.html)
- [Diseño, procedencia y huellas de los insumos](design.json)
- [Predicción y alternativas de cobertura](forecast/forecast.json)
- [Métricas y liquidaciones en JSON](report.json)

## Reproducción

El código y las fuentes archivadas de partida corresponden al commit `24ee86f`. Copie los dos scripts de este directorio a una carpeta de trabajo nueva. Con el paquete instalado, ejecute estos comandos desde la raíz del repositorio y sustituya `<trabajo>` por la ruta de esa carpeta.

```text
python <trabajo>/prepare_j20.py
python scripts/plan_spain.py --fixtures <trabajo>/fixtures.json --pleno <trabajo>/pleno.json --dataset <trabajo>/matches_j20_before_20261107.parquet --config configs/quiniela_dynamic_candidate.json --cutoff 2026-11-07 --draws 64 --budget 5.00 --output-dir <trabajo>/forecast
python <trabajo>/evaluate_j20.py
```

El segundo paso se puede repetir usando directamente los insumos archivados y una carpeta de salida nueva. Las marcas de tiempo y las rutas absolutas del pronóstico identifican la ejecución que lo produjo.
