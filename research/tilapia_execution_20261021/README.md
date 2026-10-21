# ML de crecimiento ejecutado: 21 de octubre de 2026

El candidato seleccionado es **Random Forest supervisado sobre ganancia de peso por intervalo**, versión `TILAPIA_SUPERVISED_INTERVAL_ML/0.2.0-experimental`. Se ejecutaron entrenamiento, selección, evaluación local, refit y una API interna en `vmi2770917`. No es una certificación de precisión productiva.

## Resultado biológico

La selección comparó 12 variantes: Ridge, Random Forest y Extra Trees; objetivo de ganancia absoluta o logarítmica; con y sin ambiente. Se usaron 42 intervalos externos, reteniendo estudios completos. Los donantes permanecen **provisionales** por los conflictos de fuente ya documentados. Solo hay dos estudios externos, por lo que la selección no acredita transferencia mundial.

Se congelaron código, modelos y proyecciones antes de consultar los pesos locales posteriores a B2. La evidencia se guardó también en el servidor con hash de protocolo `004afae6bdb6374e66042321033fdb4fe8070e78da556324529fc2dc4d25aaf9`.

Evaluación temporal con actualización únicamente desde biometrías anteriores, en los cuatro pesos reservados y no leídos antes de congelar **esta ejecución**:

| Variante | Fechas | MAE (g) | MAPE (%) |
| --- | ---: | ---: | ---: |
| RF seleccionado: peso inicial y duración | 4 | 14,369 | 14,678 |
| Tendencia lineal reciente | 4 | 17,103 | 16,000 |
| Persistencia del peso | 4 | 17,371 | 13,776 |
| RF con ambiente observado posteriormente | 4 | 14,935 | 15,302 |
| RF con escenarios basados en pronósticos ambientales | 3 de 4 | 17,703 | 18,657 |

El RF seleccionado reduce el MAE aproximadamente 16 % frente a la tendencia. Persistencia gana en MAPE. La rama ambiental no supera al seleccionado; tiene una fecha sin proyección por entrada faltante. Comparar modelos con distinto número de fechas requiere conservar ese fallo, no ocultarlo. B3, ya conocida por el documento, se informa aparte y también se conserva en la evaluación completa.

Las proyecciones fijas desde B2 hasta las fechas de agosto-octubre **fallaron**: MAE del RF 72,765 g frente a 42,941 g de la tendencia. No se presenta una actualización recurrente como un pronóstico fijo de todo el ciclo. La mayor desviación del RF recurrente en las cuatro fechas reservadas fue aproximadamente 36,32 g; no hay garantía de uniformidad.

El archivo de evaluación llama `selected_reconstruction` a una variante por consistencia de esquema. Su modelo tiene `environmental=false`: esos números NO dependen del ambiente futuro. La reconstrucción de la variante ambiental sí usa ambiente posterior y se etiqueta como tal. Una salida de `selected_scenario` puede faltar porque esa ruta de comparación exige el contrato completo de sensores; la inferencia directa del modelo sin ambiente sigue disponible.

## Sensores y disponibilidad

Se prepararon 6.630 promedios horarios de la base real, con marca de final de hora. Se evaluaron horizonte de una hora y media de las próximas 24 horas. La selección temporal utiliza embargo de etiquetas futuras. Persistencia fue la mejor referencia en la mayoría de salidas; Ridge mejoró OD a 24 horas en su partición de prueba. No se obliga a activar RF ambiental si no supera esas referencias.

La API ambiental consume salidas de temperatura, OD y pH con emisión, corte de entrenamiento, vigencia y versión. Nitrato nativo sirve como variable contextual de los modelos ambientales, sin atribuirle un efecto de crecimiento ni una unidad química no verificada. Los donantes no permiten aprender de forma defendible un coeficiente propio de nitrato.

La base tiene registros cargados días después de su fecha de medición. Esta evaluación es un **replay histórico por fecha de medición**, no un archivo de pronósticos que existían entonces. La zona horaria y la hora de muestreo original tampoco quedan verificadas por las fechas de biometría; se usa medianoche UTC solo como convención de ordenamiento.

El último dato ambiental disponible al comprobar el servidor estaba fechado el 4 de octubre. La rama ambiental actual informa que no está lista; no se rellena el hueco de más de dos semanas con observaciones inventadas.

## Modelo final y API

Después de terminar la evaluación, se reajustó el mismo algoritmo con los 42 intervalos donantes y los seis intervalos locales: **48 intervalos**, siete biometrias locales y 220 registros de detalle existentes. El reajuste no vuelve a contarse como prueba independiente ni se usa para reescribir resultados pasados.

La inferencia usa JSON portable, sin cargar pickles enviados por usuarios. Su equivalencia numérica con sklearn se verificó antes de evaluar y mediante pruebas con valores nuevos.

Rutas incorporadas al backend:

* `GET /api/v1/models/tilapia-growth-ml/status`
* `POST /api/v1/models/tilapia-growth-ml/predict`
* `GET /api/v1/ponds/1/models/tilapia-growth-ml/forecast?projection_days=1`

El último endpoint consulta la biometría real de la piscina y calcula automáticamente la proyección. Conserva fecha del peso observado, edad del ancla, salida de dominio, ausencia de intervalo predictivo calibrado y `production_ready=false`. No cambia la fecha de un peso antiguo para presentarlo como una medición actual.

En `vmi2770917`, el servicio `tilapia-growth-ml-pilot.service` está habilitado, con escucha en `127.0.0.1:8012` **dentro de `aquaculture_backend`**. La verificación real devolvió HTTP 200, leyó la biometría 7 (100 peces, 150,53 g de media el 16/10) y produjo aproximadamente 155,44 g para las siguientes 24 horas desde la emisión del 21/10. Ese valor sigue sin peso futuro observado para validarlo; además, el intervalo total desde el ancla quedó ligeramente por debajo del mínimo de entrenamiento de siete días.

El servicio es un piloto interno, no una nueva versión pública del panel Laravel. La rama contiene la integración de rutas para el backend principal. Los scripts `install_pilot.py` y `stop_pilot.py` restauran/detienen solamente el proceso del piloto y rechazan sobrescribir código distinto.

## Reproducir

El paquete privado de ejecución contiene datos de entrada, pesos revelados, hashes, predicciones y artefactos. No se publican esos datos locales automáticamente con el código.

```bash
python -m research.tilapia_execution_20261021.run_execution prepare \
  --sensors /ruta/hourly_sensors.json.gz --out /ruta/nueva_corrida
python -m research.tilapia_execution_20261021.run_execution evaluate \
  --sensors /ruta/hourly_sensors.json.gz \
  --labels /ruta/revealed_biometrics.json --out /ruta/nueva_corrida
python -m pytest
```

La reproducción actual ya conoce los pesos; no se denomina una nueva prueba ciega. La ejecución original conserva su evidencia congelada previa a consultarlos.

Validación de software: **105 pruebas aprobadas**. Prueba en servidor: carga del modelo, consulta de biometría real, predicción actual, replay ambiental y rechazos HTTP 422 ante horizonte sin soporte o replay presentado como pronóstico actual. Las pruebas de software no certifican exactitud biológica.

Fuentes donantes y sus controles: `research/tilapia_growth_20261021/README.md`. Los archivos de Satiro con duración pendiente no se utilizaron para supervisar crecimiento por intervalo.
