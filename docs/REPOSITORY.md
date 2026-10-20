# Organización y publicación — 20 de octubre de 2026

Se conserva la estructura de ejecución existente para mantener rutas, protocolos,
registros e identificadores históricos. La organización añade índices de navegación
y una portada actualizada. El README anterior se archiva en `PROJECT_HISTORY.md`.

## Qué contiene Git

- Código, comandos, pruebas, configuraciones, ejemplos y documentación.
- Datasets procesados y auditorías.
- Predicciones y resultados de investigación, incluidas sus métricas desfavorables,
  estados pendientes, protocolos, fuentes de código y paneles.
- `publication_manifest_20261020.json`: inventario SHA256 de los datasets y
  artefactos publicados en esta entrega.

Las credenciales, `.env`, entornos Python, cachés y capturas de `data/raw/` e
`interim/` permanecen excluidos. El manifiesto no incluye ni lee la clave DPAPI.

## Integridad y reproducción

`.gitattributes` desactiva la conversión automática de finales de línea. Los hashes
de los protocolos corresponden a bytes exactos; convertir LF/CRLF al clonar o
publicar invalidaría esa evidencia.

Los snapshots de código dentro de `outputs/` son evidencia histórica y no módulos
que deban refactorizarse con el código activo. Algunas referencias de procedencia
guardan la ruta absoluta del ordenador donde se ejecutó la investigación. Se
conservan para no reescribir registros; los comandos nuevos deben ejecutarse desde
la raíz del clon, usando rutas relativas.

Los resultados archivados permiten inspección y comparación sin volver a entrenar.
Repetir un experimento requiere sus entradas y dependencias; las versiones admitidas
están declaradas en `pyproject.toml`, pero no se promete igualdad numérica entre
cualquier versión de biblioteca o plataforma.

## Trabajo futuro

Crear nuevas carpetas de salida por experimento y nuevos snapshots por actualización.
Revisar el diff antes de cada publicación y comprobar que siguen excluidas las
credenciales. Los registros prospectivos no se completan retroactivamente.
