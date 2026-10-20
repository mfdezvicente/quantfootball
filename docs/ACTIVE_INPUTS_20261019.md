# Datos activos y control previo — 19 de octubre de 2026

El manifiesto `configs/active_inputs.json` fija el dataset, su auditoría y la configuración mediante SHA256. Los comandos de planificación y evaluación dejan de escoger silenciosamente los antiguos archivos de septiembre. El ciclo prospectivo también usa esta referencia si no se proporciona dataset.

El nuevo snapshot contiene 11.020 partidos: añade 27 resultados FullTime de las capturas públicas de LaLiga del informe del 19 de octubre (9 Primera, 10 Segunda, 8 Liga F). Se excluyen los dos partidos aún en juego en esas capturas. El corte exclusivo es el 19 de octubre; las tres ligas llegan hasta el 18. No se han descargado nuevas cuotas ni consumido créditos.

## Uso

Desde la raíz del repositorio, con el entorno Python del proyecto:

```
python scripts/check_active_inputs.py
```

Devuelve JSON y código 0 si pasa; 2 si queda bloqueado. Verifica hashes, coherencia de auditoría, validación de partidos, configuración por liga y antigüedad del último resultado anterior al corte. El límite operativo inicial es 14 días por liga. No prueba que estén todos los partidos: un parón largo exige revisar la situación y documentar cualquier cambio del límite.

`plan_spain.py` usa datos/configuración activos cuando no se indican. Toda observación oficial exige el control de antigüedad. Un análisis histórico con ambos argumentos explícitos conserva su corte y no exige actualidad. El informe de pronóstico guarda el diagnóstico y el hash del manifiesto utilizado. No sustituye las validaciones de cierre o disponibilidad de cuotas.

`probability_registry.py evaluate` usa el snapshot activo por defecto. No aplica antigüedad a una evaluación de resultados históricos; permite `--dataset` para reproducir evaluaciones anteriores.

`run_prospective_cycle.py` conserva el comparador y presupuesto de 5 euros del protocolo 50/50. Comprueba su hash antes de entrenar y registra el control previo. Si falla después de registrar la abstención, guarda el motivo en run_status.json. Requiere una observación oficial futura y cuotas actuales aportadas al comando; no es un programador automático.

## Límites y próximos pasos

La actualización no cambia el modelo ni demuestra una mejora predictiva o económica. El nuevo dataset no existía antes de la captura: no puede utilizarse para registrar a posteriori la J14 como prospectiva. Las liquidaciones oficiales pendientes siguen pendientes.

Al publicar otra versión: crear un nuevo snapshot con su auditoría, revisar resultados excluidos y cobertura, actualizar las tres referencias del manifiesto con sus hashes y ejecutar el control previo. Los archivos anteriores permanecen disponibles.

Próxima prioridad operativa: identificar el siguiente boleto elegible, verificar cierre/orden oficial y capturar cuotas antes del cierre para iniciar la cohorte 50/50. La estimación de rentabilidad sigue condicionada a datos fiables sobre participación y premios.
