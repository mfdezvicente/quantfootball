# Datos

`processed/` contiene los datasets y auditorías utilizados por los experimentos.
`configs/active_inputs.json` identifica el snapshot activo y sus hashes SHA256.
Los snapshots anteriores se conservan para reproducir las comparaciones.

`raw/` e `interim/` permanecen locales y excluidos de Git. Incluyen capturas de
proveedores, materiales originales y, dentro de `raw/credentials/`, la clave cifrada
asociada al perfil de Windows. Ninguna credencial se publica.

Los resultados y predicciones derivados están en `outputs/`. Los archivos de auditoría
conservan referencias a las capturas originales; que exista un hash no significa que
esa captura forme parte del repositorio publicado.

Para recuperar el histórico fijado de OpenFootball:

```powershell
python scripts/fetch_spanish_snapshot.py
```

El comando usa los manifiestos de `configs/source_snapshots/` y comprueba los hashes
antes de aceptar los archivos. Otras capturas dependen de la disponibilidad y las
condiciones de su proveedor. Un clon permite inspeccionar y reevaluar los artefactos
publicados; no garantiza reconstruir cada captura externa que existió localmente.

La primera ejecución operativa debe comprobar la actualidad:

```powershell
python scripts/check_active_inputs.py
```

No usar los resultados actuales para reconstruir una decisión histórica como si se
hubiera registrado antes del cierre.
