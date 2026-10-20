# Cobro conjunto de columnas bajo escenarios de premios

Se añade un evaluador económico condicional separado del modelo probabilístico y de los registros prospectivos. No cambia las columnas ni selecciona una estrategia retrospectivamente.

## Qué calcula

Para hasta seis columnas distintas y catorce partidos, calcula la distribución conjunta del dinero cobrado, P(cobrar), P(recuperar el gasto), P(beneficio), P(empatar económicamente), media neta y ROI condicional. Utiliza céntimos enteros para distinguir recuperación exacta de beneficio. Exige premios explícitos para todos los números de aciertos: un premio desconocido no se convierte en cero.

Los partidos se suponen independientes condicionalmente a sus probabilidades. Las columnas NO son independientes: todas comparten los mismos resultados. Se convolucionan los aciertos de las posiciones comunes y se enumeran las posiciones diferentes. El resultado es exacto bajo esos supuestos, incluso si varias columnas cobran simultáneamente.

No estima premios futuros, participaciones del público, recaudación, bote, Pleno ni impuestos. No incorpora incertidumbre del modelo. Las tablas de premios son escenarios exógenos, sin probabilidades asignadas, y no constituyen intervalos de confianza.

## Ejemplo retrospectivo J12

Se mantienen las probabilidades y cinco carteras originales, con premios secundarios de J12 multiplicados por 0,5, 1 y 2. Son quince comparaciones. La tabla central usa premios publicados después de los partidos, pendientes de verificación directa oficial. El partido abandonado tampoco sigue el mecanismo deportivo supuesto por la previsión: este ejercicio no es una validación económica de J12.

Para las seis columnas principales (4,50 €):

| Premios supuestos | P(cobrar) | P(recuperar gasto) | Neto medio condicionado |
|---|---:|---:|---:|
| Mitad de los de J12 | 6,88 % | 1,88 % | −1,69 € |
| Los de J12 | 6,88 % | 3,00 % | +1,11 € |
| Doble de los de J12 | 6,88 % | 6,88 % | +6,73 € |

La media positiva central no demuestra ventaja: mezcla probabilidades originales con premios conocidos a posteriori, fijos para todos los posibles resultados. Los premios reales dependen del resultado y del número de acertantes. La probabilidad de perder dinero en ese escenario central es aproximadamente 97 %. La pérdida provisional realmente observada de J12 sigue siendo 4,50 €.

## Uso

Desde la raíz del repositorio y con sus dependencias instaladas:

```powershell
$env:PYTHONPATH='src'
python scripts/compare_payout_scenarios.py --forecast outputs/predictions/registry/2026_j12/forecast.json --prize-scenarios configs/payout_sensitivity_j12.json --output-dir outputs/reports/payout_sensitivity_j12_nueva
```

La carpeta de salida debe ser nueva. Incluye HTML y JSON con distribuciones completas y hashes de entradas/código. La configuración de ejemplo contiene las restricciones y procedencia; nunca debe presentarse como tabla de premios de una jornada futura.

## Comprobaciones realizadas

Se contrastó con enumeración exhaustiva independiente de todos los resultados para seis tamaños de problema (1–6 partidos), incluyendo columnas sin posiciones comunes. Se comprobó también la identidad de la esperanza con las distribuciones marginales de aciertos, el caso determinista de recuperación exacta, ausencia de premios y rechazo de tablas incompletas. Ruff pasó para los dos archivos nuevos. Se ejecutaron las quince comparaciones del ejemplo.

## Siguiente prioridad

Registrar una previsión base y el candidato fijo 50/50 con cuotas antes del cierre de un nuevo boleto elegible. La mejora económica necesita además escenarios de premios establecidos antes de conocer resultados y datos de participación/recaudación. Hasta entonces, este evaluador sirve para sensibilidad y diagnóstico; el criterio registrado P(14) sigue vigente. No se debe optimizar una cartera con los premios de J12 y contar esa selección como mejora validada.
