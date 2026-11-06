# Protocolo auditable · comparación SISMAPISCIS

## Origen de los insumos

- VMI: `vmi2770917`, carpeta privada de validación `tilapia_validacion_fechas_20261024`.
- Reejecución base: `runs/20261025T012550344753Z`; extracción de origen con SHA256 en `cohort.json`.
- Fuente de ML: copia byte a byte de `source/interval_ml.py` del conjunto anterior.
- Fuente de TGC/VBGF: formulaciones `backend/growth_two_point_real_formulas_20260930.py` y `backend/growth_vbgf_two_point_20260930.py`; **no** se copió su calibración inicial para los períodos posteriores.
- Se incorporaron estadísticos biométricos (media, n, DE) sin pesos individuales y resúmenes elegibles de cada intervalo (temperatura media, OD medio, OD P10, pH, duración, cobertura).
- `reference_replay.json` proviene de `evidence/replay_predictions.json` y actúa como **testigo de regresión**, nunca como valor de salida del modelo.

## Entrenamiento / evaluación

Para cada intervalo objetivo `i` con `i >= 2`:
1. Se fijan como entrenamiento únicamente los intervalos `0 ... i-1`, y el peso observado de su última fecha. No se utiliza el peso biométrico del final del intervalo objetivo para ningún ajuste.
2. Se obtiene el resumen IoT de ese intervalo con `created_at`. Se exige cobertura de temperatura, OD y pH de al menos 70 % y la bandera `eligible`; los resúmenes históricos fueron previamente auditados también con hueco final no superior a 48 h.
3. Se ajusta y ejecuta el Ridge con las variables `initial_weight_g`, `duration_days`, `temperature_mean`, `oxygen_mean`.
4. Se ajusta y ejecuta el GP correlacionado con `initial_weight_g`, `duration_days`, `temperature_mean`, `oxygen_p10`.
5. Se calibra TGC con la suma de exposiciones ambientales **del prefijo**, no del objetivo: 
   - `E_i = duration_days * max(temperature_mean - 15.5,0) * f_OD(oxygen_mean)`
   - `C_i = (W_i^(1/3) - W_B1^(1/3)) / sum(E_0 ... E_(i-1))`
   - `TGC_i = [W_i^(1/3) + C_i * E_i] ^ 3`
6. Se calibra VBGF con `W_inf = 392.32 g`, `A = W_inf^(1/3)`, `TREF = 13.245267797152454`:
   - `K_i = -ln[(A-W_i^(1/3))/(A-W_B1^(1/3))] / [sum(E_0 ... E_(i-1)) / TREF]`
   - `VBGF_i = [A - (A-W_i^(1/3))*exp(-K_i*E_i/TREF)] ^ 3`
7. Se comparan los cuatro pesos estimados con la **misma** etiqueta observada y se calculan MAE, RMSE, sesgo y máximo error absoluto.
8. Se verifica cada nueva predicción Ridge/GP contra el replay congelado, tolerancia absoluta **0,001 g**.
9. El gráfico enseña B1, B2 y B3 como pesos observados; B3 actúa como único anclaje visual para TGC/VBGF. Las cuatro predicciones se presentan desde B4.

`f_OD` es la interpolación lineal de la razón experimental media `(1.24/1.75 + 2.99/4.23)/2` a OD de 3 mg/L hasta 1 a OD de 5,5 mg/L, con valores acotados fuera de este tramo.

## Limitaciones y auditabilidad

Los modelos matemáticos aquí son **adaptaciones cronológicas** de las fórmulas anteriores. No representan el pronóstico sin recalibración emitido el día de la primera biometría. La entrada ambiental del intervalo objetivo solo es conocida una vez cerrado; los cuatro sistemas producen, por tanto, estimaciones retrospectivas al cierre. La inspección de la curva original acumulativa TGC (2 200,48 g al 16/10) es un resultado de otro protocolo y no se mezcló con esta figura.

La inferencia del modelo GP calcula una desviación latente condicional, pero no intervalos de confianza con cobertura empírica demostrada. Las tres primeras biometrías iniciales solo proporcionan dos incrementos; no equivalen a tres ejemplos independientes. No se suministran lecturas IoT crudas ni datos personales.

Para una auditoría independiente se recomiendan otras campañas, contraste de relojes físicos y validación de predicciones emitidas antes del intervalo, usando su clima y oxígeno futuros medidos solo como controles ex post.
