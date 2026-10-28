# Continuación operativa — 28 de octubre de 2026

## Resultados y datos

Se capturan 32 páginas públicas de jornadas de LaLiga (Primera 1–11, Segunda 1–12 y
Liga F 1–9). El nuevo snapshot contiene 11.052 resultados: añade 12 de Primera,
12 de Segunda y ocho de Liga F. Llegan hasta el 26 de octubre en hombres y hasta el
25 en mujeres. Se conservan íntegros los registros anteriores.

La auditoría encuentra todos los resultados finales elegibles observados en esas
páginas: 99 de Primera 2026–27, 121 de Segunda y 64 de Liga F. El encuentro
abandonado sigue excluido del entrenamiento. Esta cobertura no certifica partidos
que el proveedor no haya mostrado. El manifiesto activo pasa los controles de hash
y antigüedad; el histórico anterior no se reemplaza.

## J14: escrutinio y retorno hipotético

La nueva observación primaria SELAE publica signos `2X2X121X211121`, Pleno 1–1,
premio de diez de 0 € y premio de once de 2,22 €. El sistema completo guardado
(12 columnas, coste 9 €) tiene cuatro de diez: cobro 0 €, neto −9 €.
La cartera individual (13 columnas, 9,75 €) tiene tres de once y cuatro de diez:
cobro 6,66 €, neto −3,09 €, ROI hipotético −31,69 %. Todas las demás carteras
guardadas permanecen visibles en el panel y también pierden.

No hay compra verificada ni registro prospectivo de J14. Esta liquidación hipotética
no entra en el ROI de la cohorte de decisiones. Los importes son brutos publicados,
sin simular impuestos ni la dilución del premio por añadir un acertante contrafactual.

Fuente primaria: https://www.loteriasyapuestas.es/es/la-quiniela/escrutinios/la-quiniela-premios-y-ganadores-del-18-de-octubre-de-2026

Se conserva asimismo una observación primaria del escrutinio J16: diez 1,63 € y
once 5,61 €. No existe un pronóstico congelado de esa jornada para evaluarlo ahora
como si se hubiera registrado antes del cierre.

Fuente primaria: https://www.loteriasyapuestas.es/es/la-quiniela/escrutinios/la-quiniela-premios-y-ganadores-del-25-de-octubre-de-2026

## Nuevas observaciones prospectivas

The Odds API proporciona 21 partidos masculinos futuros, diez de Primera y once
de Segunda. La captura consume dos créditos; el saldo reportado es 494. Se genera
y sella una comparación modelo/mercado antes del inicio de todos ellos, con 64
remuestreos. Es la cohorte independiente por partidos, sin boleto, Pleno ni ROI.

El archivo anterior conserva 24 comparaciones únicas ya terminadas y un abandono
excluido. Primera tiene nueve casos (log loss modelo 0,8634, mercado 0,8112) y
Segunda quince (1,0377 y 0,9918). El mercado mantiene mejor log loss en esa muestra
pequeña; los 21 nuevos partidos están pendientes. No se ajustan modelos usando
estos resultados ni se añaden cuotas femeninas inexistentes.

La cohorte 50/50 de boletos continúa en cero registros. Los concursos J14/J16 no se
registran retroactivamente ni se convierten ahora en abstenciones prospectivas.
El protocolo conserva presupuesto de 5 € y final exclusivo del 1 de julio de 2027.

## J18: preparación y bloqueo restante

El aviso corporativo oficial de SELAE confirma cierre el sábado 31 de octubre a
las 14:00, hora de Madrid. Los quince cruces propuestos están contrastados con las
páginas de LaLiga; los diez masculinos de las primeras catorce posiciones coinciden
también en identidad, fecha y hora con las cuotas capturadas. La preparación calcula
64 remuestreos y carteras hasta 10 € con la configuración actual.

El orden procede de fuentes secundarias y sigue provisional: la descarga directa
del ZIP de composición oficial devolvió HTTP 403. No se ha eludido esa restricción.
El aviso y los escrutinios se observaron mediante la herramienta web; sus descargas
directas también devolvieron 403, por lo que no se afirma disponer de sus originales
completos. Se conservan hechos estructurados y diagnósticos de acceso.

Para sellar la pareja J18 hace falta confirmar el orden contra el boleto oficial.
Después deben comprobarse otra vez cierre, horarios, antigüedad del pronóstico y
cuotas; una captura de hoy puede caducar antes del sábado. La acción económica
continúa siendo abstenerse por falta de evidencia económica validada.

## Correcciones y comprobaciones

Se corrige `ResultLookup`: también en una coincidencia de fecha exacta exige que
el registro preceda al inicio real conocido. Cuando el registro y el partido están
en el mismo día de Madrid, una hora desconocida requiere revisión; las fechas
cambiadas conservan su control. Horas ambiguas por cambio de horario se rechazan.

El actualizador histórico que sobrescribía una salida fija se sustituye por un alias
de `refresh_dataset.py`, que exige base, captura, corte y salida explícitos y rechaza
sobrescrituras. La guía documenta ese flujo y la selección explícita de la cohorte
50/50 al evaluar. Una prueba histórica se fija a sus snapshots concretos para que
actualizar el manifiesto no cambie el experimento que comprueba.

La suite completa supera 215 pruebas. Se mantienen los modelos y los archivos de
predicción congelados por el protocolo. El panel y el JSON reúnen cobertura,
liquidación hipotética, predicciones futuras y bloqueos sin mezclarlos en un ROI.

Panel: `outputs/reports/continuation_20261028/dashboard.html`.

Próximo paso: confirmar el boleto oficial J18 y registrar una pareja válida antes
del cierre; después evaluar resultados nuevos. Sigue pendiente desarrollar y
contrastar el modelo conjunto de participación y premios antes de buscar una
cartera económica con dinero real.
