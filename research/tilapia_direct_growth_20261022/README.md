# ML directo de sensores a ganancia de peso — 22/10/2026

Se implementó y entrenó un único regresor por modalidad que recibe lecturas de
temperatura, oxígeno y pH, peso inicial observado y duración, y devuelve directamente
la **ganancia de peso en gramos**. No invoca pronosticadores de sensores, el modelo
anterior de crecimiento, un meta-modelo de corrección ni una ecuación biológica de
crecimiento. El modelo anterior se usa solo como comparador en la evaluación.

La etiqueta objetivo es la diferencia entre dos medias de peso realmente medidas.
Sumar el peso inicial y la ganancia ML solo expresa el peso final; no determina el
crecimiento mediante otra fórmula. No se predice una tasa que después se multiplica
por tiempo. No se crean etiquetas diarias interpoladas.

## Entradas y semántica

La preparación calcula media, desviación estándar poblacional, mínimo, máximo,
cambio último-primero y proporción de horas observadas. Son estadísticas de entrada,
no modelos intermedios. Imputación y escala se ajustan en el entrenamiento.

- `forecast`: usa los siete días de sensores **anteriores** a una biometría recién
  observada y pronostica la ganancia hasta un objetivo futuro. Ancla y emisión deben
  coincidir. No utiliza lecturas posteriores al origen.
- `nowcast`: estima la ganancia **ya experimentada**, usando sensores medidos entre
  la biometría inicial y el instante del peso estimado. Objetivo y emisión coinciden.
  No se presenta como un pronóstico emitido antes de esas lecturas.

La API recibe medias horarias medidas, con horas únicas y zona explícita. Rechaza
lecturas futuras y disponibilidad declarada posterior a la emisión. No acepta una
variable `sensor_forecasts` de otros modelos. Se reutilizan solo rutinas genéricas
de serialización y recorrido de árboles, no artefactos de modelos intermedios.

## Datos y entrenamiento

Se mantienen siete biometrias de un lote. El snapshot anterior se actualizó desde
el 04/10 18:00 del reloj almacenado: 34.819 lecturas de agua, una fechada en 2000 y
excluida del agregado, y 2.379 de luz. La suma de conteos horarios es 34.818. No se
afirma haber revalidado todas las filas antiguas con una exportación completa nueva.
El snapshot conserva el hash del padre y la actualización de cola. SHA256 actual:
`c699041eb5a65b267533f958e44cacc06aede2670317d931934b51ad92b858f4`.

Se crean pares de extremos realmente observados hasta 60 días. Son correlacionados
cuando comparten pesos; no son nuevas biometrias. Cada fecha objetivo recibe igual
peso total en el ajuste, cualquiera que sea su número de pares. Se exige 70% de
horas observadas por cada sensor de agua, sin rellenar huecos como si fueran medidos.
Quedaron 9 pares/6 fechas objetivo para `forecast` y 7 pares/5 fechas para `nowcast`.
El último intervalo al 16/10 queda fuera de `nowcast` por cobertura insuficiente.

Para incorporar un grupo de sensor se exige variación y tres fechas objetivo con
cobertura suficiente dentro del entrenamiento. Es una regla de este experimento,
no un umbral universal de validez. **Luz no tiene ese soporte**: solo el último
origen de pronóstico tiene historial semanal suficiente. Nitrato se excluye por
unidades no verificadas. Recibir una columna de luz no significa aprender su efecto.

Se probaron cinco recetas: Ridge alfa 1/10/100, RandomForest y ExtraTrees de 120
árboles, profundidad 2 y hoja mínima 2. Para cada comparación exterior, se elige por
errores de validación de fechas anteriores al origen. Todo ajuste usa pares cuya
fecha objetivo no supera su origen de evaluación. Validación desde dos fechas
objetivo previas; evaluación exterior desde tres. El soporte de columnas también
se calcula dentro de cada entrenamiento, sin mirar al bloque que se compara.

Después se reajusta con todos los pares elegibles. El modelo final de pronóstico
eligió ExtraTrees y el de estimación RandomForest. Sus árboles utilizan realmente
temperatura, oxígeno y pH. No se declara uso de una columna solo por estar presente.

| MAE en gramos; mismas fechas dentro de cada columna | Forecast: 3 fechas | Nowcast: 2 fechas |
|---|---:|---:|
| ML directo con sensores | 19,7578 | 25,1586 |
| ML sin sensores, misma receta de cada ajuste | 11,9357 | 17,3768 |
| ML sin sensores, selección independiente | 14,1087 | 17,3768 |
| Modelo anterior de crecimiento | 7,3657 | 6,7068 |
| Tendencia reciente | 14,5499 | 16,3580 |
| Peso sin cambio | 22,0083 | 21,1225 |

Forecast compara 13/09, 26/09 y 16/10; nowcast, 13/09 y 26/09/2026. Se recalcula el
error del modelo anterior en esas mismas fechas, sin mezclar su MAE de cuatro
fechas. El error de ganancia y de peso final coincide al sumar el mismo peso inicial.

**El enlace ML directo está implementado y entrenado, pero añadir sensores no
mejoró esta prueba.** Queda como candidato sin reemplazar el panel. Estos datos y
etiquetas ya habían sido examinados: es desarrollo retrospectivo de un lote, no
una nueva validación ciega ni prueba de causalidad biológica. La separación temporal
no elimina el conocimiento previo ni la falta de campañas independientes.
Los horizontes observados parten de 13 días; horas o pocos días son extrapolación.
La inferencia informa variables fuera del rango de entrenamiento.

## Servicio y comprobaciones

El piloto privado autenticado incorpora, bajo `/api/v1`:

- `GET /models/tilapia-growth-direct/status` — arquitectura, soporte y errores.
- `POST /models/tilapia-growth-direct/predict` — contexto y lecturas horarias a
  ganancia ML directa. Modos `current` y `retrospective_fit_diagnostic`.

El diagnóstico puede reutilizar etiquetas de entrenamiento y lo informa; su HTTP
200 no es validación. `current` exige la configuración confiable de servidor
`TILAPIA_DIRECT_CLOCK_VERIFIED=1`, que solo debe habilitarse tras verificar relojes
físicos y disponibilidad. No se habilitó. Agua y recepción siguen discrepando;
faltan horas recientes alineadas con la última biometría. UTC en un diagnóstico
de orden temporal no calibra los relojes ni demuestra disponibilidad histórica.

En vmi2770917 quedaron fuentes, artefactos y evidencia en
`/root/flask_sismapiscis/aquaculture_backend/backend/research_runs/20261022_direct_sensor_growth/`.
Se respaldaron y verificaron fuentes anteriores antes de actualizarlas. Solo se
reinició el piloto; el backend público y su artefacto de crecimiento se preservan.
El registro horario archiva el estado del directo.

143 pruebas de software aprobadas. Estado HTTP 200; dos llamadas diagnósticas HTTP
200 con igual resultado que la inferencia local; sin clave 401; modo actual sin
verificar relojes 503. Artefacto anterior intacto. Se sirven parámetros JSON, sin
pickle ni ejecución de submodelos de sensores. Son comprobaciones de implementación.

## Reproducir y revertir

Instalar `requirements-training.txt`; desde la raíz del repositorio:

```bash
PYTHONPATH=. python research/tilapia_direct_growth_20261022/train_direct.py --snapshot /privado/snapshot.json.gz --previous-predictions /privado/local_predictions.json --out /privado/evidence
python -m pytest
```

Los datos locales, peticiones, artefactos entrenados y filas de evaluación quedan
fuera de Git. Se contrasta sklearn contra JSON para todos los pares reales. Los
tests verifican ventanas temporales, cobertura, duplicados, rechazo de pronósticos
externos y dependencia numérica de sensores en fixtures; no demuestran efectos
fisiológicos. Para revertir, restaurar `pilot_service.py`, `install_pilot.py` y
`capture_prospective.py` de `previous_serving_sources/` y reiniciar solo el piloto.
Conservar las emisiones archivadas. El artefacto previo no fue sustituido.

Documentación primaria: [prevención de filtración](https://scikit-learn.org/stable/common_pitfalls.html)
y [separación de entrenamiento y evaluación](https://scikit-learn.org/stable/modules/cross_validation.html).
