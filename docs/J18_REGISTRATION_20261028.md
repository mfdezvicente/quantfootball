# J18 confirmada y registrada — 28 de octubre de 2026

La captura aportada por el usuario confirma las quince posiciones, los cuatro
partidos femeninos 11–14 y el Pleno Athletic Club masculino–Real Sociedad masculino.
Se conserva su SHA256 y el momento real de revisión. El recorte no muestra URL,
fecha ni número de jornada: su atribución a J18 usa el contexto de la conversación
y el cruce con los calendarios preparados. No se presenta como una descarga directa
independiente de la composición de SELAE.

## Registros efectuados antes del cierre

El ciclo usa el snapshot activo de 11.052 partidos y las cuotas capturadas hoy,
admisibles para los diez partidos masculinos combinables. No consume nuevos créditos.
Primera femenina mantiene las probabilidades del modelo propio. Se calculan 64
remuestreos con los modelos y la mezcla 50/50 previamente congelados.

- Pareja de probabilidades: `outputs/predictions/probability_pairs_pool50/2026_j18`.
- Decisión económica: `outputs/predictions/economic_decisions/2026_j18`.
- Cobertura del candidato: `outputs/predictions/coverage_pool50/candidate/2026_j18`.
- Cobertura del comparador: `outputs/predictions/coverage_pool50/comparator/2026_j18`.

La pareja conserva sus catorce partidos pendientes. Las dos carteras tienen seis
columnas independientes y coste teórico 4,50 € por alternativa, dentro del máximo
original de 5 €. La estrategia principal `individual_columns` queda fijada antes
del resultado; no se escogerá después otra estrategia por haber cobrado más.
El Pleno previsto en ambos brazos es 1–1. Las columnas se introducen por separado
como apuestas simples al consultar la selección; este flujo no realiza compras.

Las carteras permiten liquidar posteriormente cobros hipotéticos con signos y
premios oficiales. Sus manifiestos v2 enlazan el protocolo y el sello de la pareja.
La fecha nominal es 1 de noviembre de 2026; cierre confirmado el sábado 31 de
octubre a las 14:00 de Madrid. Ambos brazos son alternativas comparables y no se
suman como gasto conjunto ni se mezclan con el registro anterior de J12.

## Decisión económica

Abstención registrada: gasto real 0 €. Faltan validación del modelo conjunto de
participación, del modelo de premios y un protocolo económico propio. El motivo
adicional `missing_probability_forecast` describe el momento inicial del registro,
anterior al cálculo: queda conservado. Los pronósticos calculados después están
disponibles en sus registros separados, sin reescribir esa decisión.

No se ha comprado boleto ni se afirma ROI esperado positivo. La comparación por
partidos y la pareja del boleto pueden compartir encuentros; no deben contarse
como observaciones independientes adicionales. El final del protocolo 50/50 se
mantiene en el 1 de julio de 2027, con revisiones intermedias diagnósticas.

## Verificación y próximos pasos

Se verifican sellos, cuotas, identidad de la observación, configuración, presupuesto,
estrategia principal y fechas. Las pruebas focalizadas de registro, ciclo y decisiones
económicas superan 55 casos. No se modifican los registros provisionales anteriores.

Panel: `outputs/reports/j18_registration_20261028/dashboard.html`.
Texto de columnas: `outputs/reports/j18_registration_20261028/selection.txt`.

Tras los encuentros, actualizar resultados finalizados y evaluar con:

```powershell
python scripts/probability_registry.py evaluate --root outputs/predictions/probability_pairs_pool50 --output outputs/reports/NUEVA_EVALUACION/pool50.json
```

La liquidación de cobertura se hará por brazo y con el extracto oficial completo,
conservando pendientes, partidos adjudicados y premios desconocidos. No convertir
un Pleno sin acertantes en premio contrafactual de cero. La abstención económica
mantiene su propio registro.
