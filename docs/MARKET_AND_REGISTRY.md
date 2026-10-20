# Mercado y registro prospectivo

Actualización: 25-09-2026.

## Qué está listo y qué falta

Se incorporaron la importación de cuotas con fechas, su comparación con el modelo,
una pestaña **Mercado** en el visor y un registro local de pronósticos anteriores
al cierre. El visor actualizado de los 61 concursos está en
`outputs/reports/market_registry_v1/dashboard.html`. La pestaña muestra claramente
la ausencia de cuotas cuando no hay un archivo importado.

**No se ha incorporado una muestra real de cuotas ni porcentajes apostados.**
La comparación cuantitativa contra el mercado y un nuevo cálculo de rentabilidad
quedan pendientes de esos datos. Los resultados anteriores de 61 concursos no
cambian: no se ha demostrado ROI positivo. Tampoco se ha registrado un concurso
futuro real con un horario oficial de cierre verificado.

## Fuente de cuotas

Football-Data publica históricos de ambas divisiones, pero su página de datos
restringe el uso automatizado con bots/scrapers/IA. En esta iteración se consultó
la documentación; **no se descargaron sus datasets para incorporarlos**.
[Descripción y condiciones de Football-Data](https://football-data.co.uk/data.php).

Una posible integración posterior es The Odds API: su documentación contempla
consultas históricas con timestamp, incluyendo LaLiga y Segunda. Requiere una
cuenta y acceso al producto correspondiente. No se ha contratado ningún servicio,
consumido créditos ni guardado claves.
[Documentación oficial del histórico](https://the-odds-api.com/historical-odds-data/).

El importador actual admite un archivo JSON de una fuente autorizada, sin depender
de un proveedor. Nunca se deben introducir claves en los archivos versionados;
las URL de procedencia se guardan sin credenciales ni parámetros de consulta.

## Comparación con mercado

Formato en `examples/market_snapshot.example.json`: **cuotas ficticias**, señaladas
como ejemplo y rechazadas por el registro prospectivo. Para un archivo real se
requieren:

- `snapshot_at`: momento al que corresponde la fotografía del mercado.
- `retrieved_at`: momento real en que se recuperó ese archivo. Descargar hoy un
  archivo histórico no significa que esta aplicación lo tuviera antes del partido.
- Por partido: división, nombres canónicos, inicio con zona horaria y cotizaciones
  con casa de apuestas, `observed_at` y las tres cuotas decimales en orden 1/X/2.
- Opcionalmente, porcentajes apostados expresados como fracciones que suman 1,
  con su propia procedencia y fecha. Se conservan separados de las probabilidades.

Para cada casa se elimina proporcionalmente el margen: `p = (1/cuota) / suma(1/cuota)`.
Después se promedian las probabilidades de las casas. Se conserva solo la última
cotización válida por casa, evitando contar varias veces a una misma entidad.
Por defecto se descartan cotizaciones de más de 48 horas respecto a la decisión.
Se rechazan fechas sin zona horaria, datos futuros, partidos de otra fecha,
duplicados contradictorios y cuotas inválidas.

```powershell
python scripts/compare_market.py --forecast outputs/predictions/mi_pronostico/forecast.json --snapshot mi_snapshot_autorizado.json --decision-at "2026-09-26T12:00:00+02:00" --output-dir outputs/reports/mi_comparacion
```

La fecha del comando es ilustrativa, **no el cierre oficial de un concurso**.
El resultado incluye JSON y HTML. No modifica las probabilidades del modelo,
no selecciona una mezcla usando los resultados posteriores y no calcula un ROI
esperado. Las diferencias con el mercado no equivalen a una ventaja demostrada.
Los porcentajes marginales apostados tampoco determinan cuántas personas poseen
una columna completa: falta la distribución conjunta para estimar el reparto.

## Registro antes del cierre

1. Generar el pronóstico con `scripts/plan_spain.py` y aportar el Pleno.
2. Completar `examples/contest_manifest.template.json` con los quince partidos
   oficiales, sus horarios, fecha del concurso y hora real de cierre. El campo
   `captured_at` debe reflejar la consulta real. Eliminar `is_example` solo cuando
   se hayan sustituido los valores de ejemplo por datos reales.
3. Elegir `primary_strategy` antes de los resultados. Las otras estrategias quedan
   como comparaciones secundarias. Se congela un solo presupuesto, como máximo 5 €.
4. Registrar mientras no haya cerrado el concurso ni comenzado ninguno de sus partidos:

```powershell
python scripts/forecast_registry.py register --forecast outputs/predictions/mi_pronostico/forecast.json --manifest mi_concurso_oficial.json
python scripts/forecast_registry.py verify --record outputs/predictions/registry/IDENTIFICADOR
python scripts/forecast_registry.py summary
```

El registro incluye copia del pronóstico y manifiesto, huellas SHA-256, hora real
del sistema y visor HTML. No admite cambiar la hora desde el CLI ni sobrescribir
un identificador existente. Comprueba presupuesto, coste real de columnas,
equipos, orden, fechas, Pleno y separación entre entrenamiento y pronóstico.
Una generación con fecha futura se etiqueta **sin registrar** hasta este paso.

El reloj y las huellas son **locales**: detectan cambios frente al sello guardado,
pero no son un sello temporal externo ni prueban que se haya apostado dinero.
La autenticidad de los horarios aportados sigue dependiendo de verificar la
fuente oficial; el programa no la certifica. No hay compra ni envío de apuestas.

## Liquidación y seguimiento

Después del cierre, importar un extracto de las tablas oficiales en el mismo
formato ya utilizado por el archivo histórico:

```powershell
python scripts/forecast_registry.py settle --record outputs/predictions/registry/IDENTIFICADOR --extract extracto_oficial.txt --source-url "https://www.loteriasyapuestas.es/es/la-quiniela/resultados"
python scripts/forecast_registry.py summary
```

El registro liquida los signos oficiales y conserva el pronóstico original; no
los reemplaza por el resultado deportivo posterior de un partido aplazado.
Guarda el extracto y un recibo nuevo. Si un premio ganador es desconocido o bote,
no inventa su importe. Una liquidación ya existente no se sobrescribe.

El resumen enumera todos los registros, incluidos pendientes e incompletos,
recalcula el premio de la estrategia principal desde el extracto guardado y
separa el coste pendiente. El ROI mostrado corresponde únicamente a registros
liquidados; se indica si la contabilidad está incompleta. Los premios siguen
siendo brutos y no incluyen impuestos ni el efecto de nuestras columnas en el reparto.

## Próxima evaluación

El conector gratuito y el primer estudio de probabilidades de clubes están
descritos en [THE_ODDS_API.md](THE_ODDS_API.md). Ese registro de catorce partidos
está separado del registro de boletos completos: las selecciones quedan fuera
del alcance acordado. Las comparaciones de mercado que se registren deben
haberse recuperado antes de su hora de decisión declarada.

Con una fuente autorizada disponible: comparar modelo y mercado sobre exactamente
los mismos partidos y el mismo momento de decisión; estudiar una mezcla con
selección temporal; después incorporar popularidad y premios para optimizar el
retorno esperado. El registro permite reunir una muestra nueva sin reutilizar
2024–26 como si fueran temporadas todavía no observadas.
