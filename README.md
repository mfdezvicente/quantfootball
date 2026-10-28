# QuantFootball

Investigación reproducible de probabilidades y estrategias de La Quiniela para
**Primera y Segunda masculinas y Primera femenina (Liga F)**.

El objetivo es investigar una posible rentabilidad positiva, incluyendo la decisión
de no apostar. **Todavía no se ha demostrado una ventaja económica.** El modo de
trabajo es simulación; el proyecto no compra apuestas.

## Estado del proyecto — 28 de octubre de 2026

- Snapshot activo: **11.052 partidos**, con resultados hasta el 26 de octubre en hombres
  y el 25 en Liga F. Se incorporan 32 resultados y se contrasta la cobertura actual.
- Modelos por competición, calibración, comparación con mercado y experimentos
  temporales de variables, redes neuronales y distribuciones de goles.
- Los últimos experimentos no justifican sustituir el modelo actual.
- Planificación de columnas, dobles y triples, riesgo conjunto y seguimiento.
- Presupuesto máximo económico: **10 €** (hasta 13 columnas por 9,75 €).
  Los experimentos históricos y el protocolo 50/50 conservan su presupuesto original.
- Comparación prospectiva 50/50 prevista hasta el **1 de julio de 2027**.
  Su protocolo y los registros anteriores permanecen congelados.
- La recomendación económica sigue bloqueada por falta de estimaciones contrastadas
  de participación conjunta y premios. Los escenarios hipotéticos no son ROI probado.

Se han sellado 21 nuevas comparaciones modelo/mercado antes del inicio. La J18
tiene cierre confirmado el 31 de octubre a las 14:00 (Madrid), pero su registro
sigue pendiente de verificar el orden oficial del boleto. La J14 preliminar habría
perdido 3,09 € en las trece columnas; no fue una compra ni un registro prospectivo.

## Empezar

Python **3.12 o 3.13**. Desde la raíz del repositorio, en PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python scripts/check_active_inputs.py
python -m pytest -q
```

El control de entradas verifica hashes y antigüedad. Un clon realizado tiempo después
puede fallar por datos antiguos: eso exige actualizar los resultados, no desactivar
el control. Los datasets procesados y los resultados archivados están incluidos.

Para una demostración con equipos ficticios:

```powershell
python scripts/plan_quiniela.py --probabilities examples/quiniela_demo.json --budget 5 --output outputs/predictions/demo_quiniela.json
```

Para estudiar los comandos operativos:

```powershell
python scripts/plan_spain.py --help
python scripts/run_prospective_cycle.py --help
python scripts/economic_registry.py --help
```

Las cuotas actuales requieren una clave propia de The Odds API.
Consulta [configuración y límites](docs/THE_ODDS_API.md).

## Estructura

| Carpeta | Contenido |
|---|---|
| `src/quantfootball/` | Datos, variables, modelos, evaluación, mercado y Quiniela |
| `scripts/` | Comandos de captura, entrenamiento, planificación y evaluación |
| `configs/` | Configuraciones, manifiestos y protocolos congelados |
| `examples/` | Ejemplos y plantillas de entrada |
| `tests/` | Pruebas y datos sintéticos |
| `data/processed/` | Snapshots y auditorías que sustentan los experimentos |
| `data/raw/`, `data/interim/` | Capturas locales y datos de trabajo excluidos de Git |
| `outputs/` | Predicciones, liquidaciones, informes y resultados de investigación |
| `docs/` | Metodología, decisiones, resultados y guía del repositorio |

## Informes y documentación

- [Avances del 28 de octubre, J14 y preparación J18](docs/CONTINUATION_20261028.md).
- [Índice de documentación](docs/README.md).
- [Índice de paneles y resultados](outputs/README.md).
- [Guía de comandos](scripts/README.md).
- [Datos y reproducción](data/README.md).
- [Organización y publicación del repositorio](docs/REPOSITORY.md).
- [Última investigación de modelos de goles](docs/GOAL_FLEX_20261019.md).
- [Diagnóstico del predictor y experimentos controlados](docs/MODEL_RESEARCH_20261019.md).
- [Auditoría de premios](docs/PRIZE_AUDIT_20261019.md).
- [Historial de actualizaciones del README](docs/PROJECT_HISTORY.md).

Los paneles HTML se pueden abrir localmente después de clonar el repositorio.
GitHub muestra su código; esta publicación no activa GitHub Pages.
