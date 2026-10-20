# Diagnóstico y experimentos controlados del predictor

Investigación retrospectiva de periodos ya inspeccionados; no constituye una mejora prospectiva ni evidencia de ROI.

## Resultado por división

Primera masculina: selección = dynamic.
- base: LL selección 0.975045; diagnóstico 0.972316; delta +0.000000; intervalo [0.0, 0.0].
- opponents: LL selección 0.974735; diagnóstico 0.972848; delta +0.000532; intervalo [-0.0011218256791386753, 0.0021378781317706068].
- dynamic: LL selección 0.974717; diagnóstico 0.971957; delta -0.000359; intervalo [-0.0018834008245439164, 0.0012076725976354642].
- rest: LL selección 0.975461; diagnóstico 0.972100; delta -0.000216; intervalo [-0.0010940932486075026, 0.0006273598457678365].
- congestion: LL selección 0.975518; diagnóstico 0.972106; delta -0.000210; intervalo [-0.0011820661442996602, 0.0006730562904314534].
- transfer: LL selección 0.974813; diagnóstico 0.972269; delta -0.000048; intervalo [-0.0007029845317068751, 0.0005845874300370964].

Segunda masculina: selección = rest.
- base: LL selección 1.048675; diagnóstico 1.044906; delta +0.000000; intervalo [0.0, 0.0].
- opponents: LL selección 1.048435; diagnóstico 1.045529; delta +0.000623; intervalo [-1.0385266020214196e-05, 0.0012249596703001419].
- dynamic: LL selección 1.049364; diagnóstico 1.045070; delta +0.000164; intervalo [-0.0006544799276184503, 0.001007662127493703].
- rest: LL selección 1.048283; diagnóstico 1.044759; delta -0.000147; intervalo [-0.0008545115383189078, 0.0007552931348023255].
- congestion: LL selección 1.049268; diagnóstico 1.044491; delta -0.000414; intervalo [-0.0013576073449370074, 0.00047454415278929627].
- transfer: LL selección 1.048365; diagnóstico 1.045730; delta +0.000824; intervalo [0.00021463722411530043, 0.0014885875474511313].

## Límites
- Historical selection/diagnostic periods were inspected before; no untouched confirmation
- New groups and fixed online-goal constants are declared now, after previous historical research
- Monthly rolling fits use only prior labels; statistical intervals do not correct repeated model selection
- League-only rest/congestion, final archived schedule dates; no cups, Europe, xG, injuries or publication-time proof
- Dynamic features are a fixed online goal-state proxy, not the existing full dynamic MAP goal model
- Controlled feature experiments are male only; Liga F diagnosed with its own frozen goal model
- No production model or the fixed prospective 50/50 protocol is promoted by this run

Ningún modelo de producción, configuración congelada o registro anterior se ha modificado. Las diferencias de este informe no habilitan recomendaciones económicas.