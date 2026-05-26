# Frontend operativo para Gemelo Digital Acuicola

Base publica:

```text
http://37.60.226.53:8000/api/v1
```

## Estado real del backend

Los modelos deterministas, mecanisticos, bioenergeticos y reglas ya tienen formula ejecutable y trazabilidad. Los modelos ML y vision tienen contrato real, entradas reales y dry-run, pero para prediccion productiva necesitan artefactos entrenados/versionados.

De los 45 componentes identificados en la arquitectura del gemelo digital, 40 tienen viabilidad tecnica alta dentro del backend actual. Esta cifra no significa que todos esten productivos de inmediato; significa que la arquitectura ya puede soportarlos mediante formula, entrenamiento tabular o integracion de artefactos.

Clasificacion operativa:

- Implementados o programables por formula: modelos de oxigeno, RAS, crecimiento, bioenergetica, zootecnia y reglas de alimentacion. El frontend debe tratarlos como ejecutables cuando `input-audit` indique `ready` y todos los inputs esten completos.
- Entrenables con la base historica tabular: LSTM, Pearson-LSTM, Pearson-LSTM-AM, BPNN-MEA y modelos ML clasicos sobre telemetria. El frontend debe tratarlos como entrenables o en dry-run hasta que exista un artefacto activo con version y metricas.
- Condicionados por datos externos: vision por imagen/video, comportamiento por tracking, distribucion de alimento por CFD/corrientes y amoniaco mecanistico sin ecuaciones completas. El frontend debe mostrarlos como modulos condicionados, no como predicciones finales.

Lectura recomendada para UI:

- `ready`: puede ejecutarse si se completan los inputs.
- `requires_external_artifact`: requiere modelo entrenado/versionado antes de prediccion real.
- `metadata_or_dry_run_only`: solo debe mostrarse como contrato, simulacion seca o pendiente de formulacion.

No usar MongoDB como supuesto visual o tecnico. El sistema operativo actual consume MySQL: lee la base legacy sin tocarla y trabaja sobre `aquaculture_digital_twin`.

El frontend no debe hardcodear formularios. Debe construirlos desde:

```text
GET /models
GET /models/{model_code}/input-audit?pond_id={pond_id}
GET /models/{model_code}/test-payload?pond_id={pond_id}
POST /models/{model_code}/test-run?pond_id={pond_id}
POST /models/test-run-all?pond_id={pond_id}
GET /frontend/dashboard?farm_id={farm_id}&pond_id={pond_id}
```

`input-audit` dice que entradas salen automaticamente de BD, que entradas faltan por formulario, que unidad exacta debe enviarse y si el modelo esta bloqueado por artefacto pendiente.

`test-payload` genera un payload completo mezclando inputs reales disponibles en BD y valores marcados como `generated_test_value` para los campos faltantes. Sirve para probar formularios, rutas y salidas sin inventar datos dentro del frontend.

`test-run` ejecuta ese payload de prueba. En modelos con artefacto pendiente agrega `dry_run`/`metadata_only` automaticamente; por eso puede validar contrato aunque todavia no exista predictor entrenado.

`test-run-all` ejecuta todos los modelos registrados con datos reales disponibles y valores generados donde falten. Debe usarse como comprobacion global del backend.

`frontend/dashboard` entrega un paquete agregado para la pantalla principal: backend online, granjas, estanques, tarjetas del mapa integral, resumen de modelos, calidad de agua actual, rutas de accion, evidencia y trazabilidad.

Importante: `models` no significa los 45 componentes del proyecto. `models` son los 13 runners ejecutables por API. Los 45 componentes completos se consultan en:

```text
GET /frontend/components
```

Ese catalogo separa:

- `total_components`: 45
- `integrable_components`: 40
- `implemented_components`: 40
- `conditioned_components`: 5
- `executable_model_runners`: 13

Los 40 no son todos endpoints `/models/{code}/run`. Los 40 estan implementados en backend como una mezcla de:

- runners ejecutables;
- funciones matematicas puras;
- algoritmos tabulares/series temporales;
- preprocesamiento y metricas;
- modulos de datos, dashboard, auditoria, trazabilidad y gemelo digital.

## Flujo principal del frontend

1. Seleccionar granja y estanque.
2. Cargar estado vivo del estanque.
3. Cargar catalogo de modelos.
4. Para cada modelo visible, pedir auditoria de inputs con el `pond_id`.
5. Renderizar formulario dinamico:
   - `auto_available`: mostrar como dato precargado desde BD, editable solo si el usuario quiere sobrescribir.
   - `form_required`: pedirlo en formulario.
   - `blocked_by`: mostrar bloqueo operativo, no como error visual.
6. Al ejecutar, enviar todos los inputs juntos, automaticos mas formulario.
7. Mostrar resultados, warnings, explicacion corta y `traceability.model_run_id`.

Payload estandar para cualquier modelo:

```json
{
  "pond_id": "LEGACY-POND-1",
  "inputs": {
    "water_temperature_c": {
      "value": 30.7,
      "unit": "degC",
      "quality_flag": "legacy_valid"
    },
    "flow_rate_l_h": {
      "value": 1200,
      "unit": "L/h"
    }
  },
  "parameters": {}
}
```

La unidad debe ser exacta. Ejemplo: `h^-1` no debe enviarse como `h-1`.

## Pantallas que debe asumir el frontend

### 0. Resumen integral del proyecto

Esta pantalla puede consumir una sola ruta agregada:

```text
GET /frontend/dashboard?farm_id={farm_id}&pond_id={pond_id}&range_label=Ultimas%2024%20horas
```

Debe alimentar:

- estado `Backend ONLINE`;
- selectores de granja, estanque y rango temporal;
- mapa integral de siete entregables;
- resumen de modelos y estados;
- calidad de agua actual;
- evidencia generada;
- tabla de trazabilidad;
- rutas disponibles para ejecutar modelos, gemelo y actuadores.

Campos principales de respuesta:

- `backend`
- `selection`
- `farms`
- `ponds`
- `system_metrics`
- `project_map`
- `component_summary`
- `components`
- `model_summary`
- `models`
- `water_quality_current`
- `timeseries`
- `digital_twin`
- `evidence`
- `traceability`
- `frontend_contract_routes`

### 1. Operacion en vivo

Primera pantalla despues de entrar. Debe verse como una consola clara de produccion, no como pagina informativa.

Debe mostrar:

- Selector de granja, estanque y rango de tiempo.
- Estado del backend.
- Ultimo valor por variable critica: oxigeno disuelto, temperatura, pH, nitratos/nitritos/amoniaco si existen.
- Grafico de serie temporal con selector de variable.
- Calidad del dato: `quality_flag`, unidad y fecha de ultima lectura.
- Acceso directo a "Ejecutar modelo" para el estanque activo.

Rutas principales:

```text
GET /health
GET /farms
GET /ponds?farm_id={farm_id}
GET /sensors?pond_id={pond_id}
GET /telemetry/clean?pond_id={pond_id}&variable_code={variable}&limit={n}
GET /telemetry/timeseries?pond_id={pond_id}&variable_code={variable}&limit={n}
GET /twin/state/{pond_id}
GET /frontend/dashboard?farm_id={farm_id}&pond_id={pond_id}
GET /frontend/components
```

### 2. Catalogo de modelos

Debe mostrar tarjetas o tabla compacta por modelo, agrupadas por familia:

- Oxigeno disuelto.
- RAS.
- Crecimiento.
- Zootecnia.
- Alimentacion.
- ML.
- Vision.

Cada modelo debe mostrar:

- Nombre.
- Codigo.
- Estado: `ready`, `requires_external_artifact`, `metadata_or_dry_run_only`.
- Entradas automaticas disponibles.
- Entradas faltantes.
- Boton "Completar y ejecutar".

Rutas:

```text
GET /models
GET /models/{model_code}
GET /models/{model_code}/input-audit?pond_id={pond_id}
GET /models/{model_code}/test-payload?pond_id={pond_id}
POST /models/{model_code}/test-run?pond_id={pond_id}
POST /models/test-run-all?pond_id={pond_id}
GET /frontend/components
```

### 3. Ejecutor de modelo

Es la pantalla mas importante. Debe unir BD y formulario.

Debe verse asi:

- Panel izquierdo: datos del estanque y ultimas mediciones usadas.
- Panel central: formulario generado desde `form_fields`.
- Panel derecho: resultado del modelo, riesgo, warnings y trazabilidad.

Reglas visuales:

- Campos automaticos: mostrar valor, unidad y fuente.
- Campos requeridos: input numerico, selector, checkbox, texto, editor JSON, serie temporal o media reference segun `control`.
- Campos con `options`: usar select.
- Boton ejecutar deshabilitado si hay `missing_inputs` sin completar.
- Si `blocked_by` contiene artefacto pendiente, permitir solo modo metadata/dry-run.

Ruta generica recomendada:

```text
POST /models/{model_code}/run
```

Rutas para probar cualquier modelo sin depender de que la BD ya tenga todos los campos:

```text
GET /models/{model_code}/test-payload?pond_id={pond_id}
POST /models/{model_code}/test-run?pond_id={pond_id}
POST /models/test-run-all?pond_id={pond_id}
```

La UI debe mostrar claramente que esos valores son de prueba cuando `quality_flag` sea `generated_test_value`.

Si un dato real de BD existe pero cae fuera del dominio matematico de una prueba, el backend cambia esa prueba a valores generados validos y lo informa en `notes`. Esto evita que el frontend parezca roto cuando la medicion real no sirve para una simulacion demo.

Tambien existen aliases clasificados:

```text
POST /models/do/simulate-0d
POST /models/do/simulate-1d
POST /models/deterministic/oxygen/0d/simulate
POST /models/deterministic/oxygen/1d/simulate
POST /models/deterministic/ras/oxygen-balance
POST /models/growth/yi/simulate
POST /models/growth/soderberg
POST /models/growth/zootechnics/calculate
POST /models/growth/brigolin
POST /models/bioenergetic/brigolin/simulate
POST /models/feeding/daily-ration/calculate
POST /models/feeding/satiety/evaluate
POST /models/feed/bpnn/predict
POST /models/ml/feed-intake/predict
POST /models/water-quality/lstm/predict
POST /models/ml/water-quality/forecast
```

## Como completar inputs por modelo

## Catalogo de 45 componentes

El dashboard debe tratar estos numeros como diferentes:

- 45 componentes auditados del proyecto completo.
- 40 componentes implementados en la arquitectura actual.
- 5 componentes condicionados por datasets externos o formulacion faltante.
- 13 runners de modelo ejecutables directamente por `/models`.

Ruta:

```text
GET /frontend/components
```

Familias del catalogo:

- `oxygen_water_quality`: 8 componentes.
- `growth_bioenergetic`: 10 componentes.
- `ml_tabular_statistics`: 11 componentes.
- `architecture_twin`: 11 componentes.
- `conditioned_external`: 5 componentes.

Campos por componente:

- `component_code`
- `family`
- `title`
- `kind`
- `viability_status`
- `implementation_status`
- `implementation_ref`
- `backend_status`
- `linked_model_code`
- `is_executable_model_runner`
- `routes`

Regla visual:

- Si `is_executable_model_runner` es `true`, el frontend puede mostrar boton de `test-run`, `test-payload` y `run`.
- Si `implementation_status` es `implemented_backend` pero no tiene `linked_model_code`, debe mostrarse como componente implementado por arquitectura, algoritmo, tabla, flujo o modulo backend.
- Si `viability_status` es `conditioned`, debe mostrarse como pendiente de datos externos o investigacion, no como falla del backend.

### DO_DYNAMIC_0D_ROYER_2021

Uso visual: simulacion de oxigeno futuro y riesgo de hipoxia.

Automatico desde BD:

- `do_initial_mg_l` desde `clean_measurements.dissolved_oxygen_mg_l`.
- `water_temperature_c` desde `clean_measurements.water_temperature_c`.
- `raceway_volume_l` desde `pond.water_volume_l`, si existe.

Formulario:

- `do_influent_mg_l`
- `flow_rate_l_h`
- `fish_biomass_kg`
- `fish_respiration_rate_mg_h_kg`
- `oxygen_supply_rate_mg_l_h`
- `reaeration_rate_h_1`
- `simulation_horizon_minutes`

### DO_TRANSPORT_1D

Uso visual: perfil longitudinal de oxigeno por segmentos.

Formulario principal:

- `concentrations_mg_l`
- `saturation_mg_l`
- `biomass_kg`
- `q_over_area_m_h`
- `reaeration_rate_h_1`
- `fish_respiration_rate_mg_h_kg`
- `area_m2`
- `dx_m`
- `dt_h`

Debe verse como editor de segmentos, no como inputs sueltos.

### RAS_OXYGEN_BALANCE

Uso visual: balance de oxigeno en sistema RAS.

Automatico si la BD lo tiene:

- `water_temperature_c`
- `average_weight_g`
- `fish_count`
- `biomass_kg`

Formulario:

- `do_previous_mg_l`
- `stocking_density_kg_m3`
- `volume_m3`
- `dt_h`

Parametros opcionales:

- `feed_rate_percent_body_weight_day`
- `bod5_mg_o2_kg_day`
- `pump_cycle_h`
- `pump_frequency_h_1`
- `pump_efficiency`
- `oxygen_transfer_rate_g_h`

### YI_ENVIRONMENTAL_GROWTH

Uso visual: crecimiento diario condicionado por temperatura y oxigeno.

Automatico si la BD lo tiene:

- `water_temperature_c`
- `dissolved_oxygen_mg_l`
- `fish_weight_g`

Formulario:

- `t_min_c`
- `t_opti_c`
- `t_max_c`
- `do_min_mg_l`
- `do_crit_mg_l`
- `k_min`
- `s`
- `kappa`
- `phi`
- `h`
- `feeding_level`
- `m`
- `n`

### SODERBERG_LINEAR_GROWTH

Uso visual: crecimiento lineal y alimento estimado por talla.

Automatico:

- `water_temperature_c`

Formulario:

- `fish_length_mm`

Parametros:

- `species`
- `feed_conversion_ratio`

### ZOOTECHNIC_INDEXES

Uso visual: cierre de ciclo, indicadores productivos y comparacion de lotes.

Formulario o registros operativos:

- `final_weight_g`
- `initial_weight_g`
- `final_length_cm`
- `days`
- `final_fish_count`
- `initial_fish_count`
- `feed_consumed_g`

Parametros opcionales:

- `biomass_removed_mortality_g`
- `biomass_sampled_g`
- `tank_to_m3_factor`

### BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010

Uso visual: crecimiento bioenergetico individual por dieta y temperatura.

Automatico:

- `wet_weight_g` desde `fish_weight_g`, si existe.
- `water_temperature_c`

Formulario:

- `feed_ration_day_1`
- `protein_fraction`
- `lipid_fraction`
- `carbohydrate_fraction`
- `protein_digestibility`
- `lipid_digestibility`
- `carbohydrate_digestibility`
- `energy_content_somatic_tissue_kj_g`

Parametro:

- `dt_day`

### DAILY_RATION_MODEL

Uso visual: racion diaria sugerida.

Automatico si la BD lo tiene:

- `fish_length`
- `fish_weight`

Formulario:

- `feed_conversion_ratio`
- `daily_growth`

### FEEDING_SATIETY_RULES

Uso visual: decision rapida durante alimentacion.

Formulario:

- `feeding_behavior_category`
- `feed_remaining`
- `fish_reaction`

Debe verse como checklist operativo, no como formulario tecnico.

Opciones:

- `ACTIVE_CONTINUOUS_FEEDING`
- `MOVE_AND_RETURN`
- `ONLY_FRONT_FEEDING`
- `NO_REACTION`

### BPNN_MEA_FEED_INTAKE

Uso visual: prediccion ML de consumo de alimento.

Automatico si la BD lo tiene:

- `water_temperature_c`
- `dissolved_oxygen_mg_l`
- `average_fish_weight_g`
- `fish_number`

Estado:

- Requiere artefacto entrenado para prediccion productiva.
- El frontend puede mostrar metadata/dry-run, pero no debe venderlo como prediccion final hasta cargar pesos.

### PEARSON_LSTM_ATTENTION_WQ

Uso visual: forecast de calidad de agua por serie temporal.

Automatico si existen series alineadas:

- `ph`
- `water_temperature_c`
- `dissolved_oxygen_mg_l`
- `ammonia_nitrogen_mg_l`
- `nitrite_mg_l`
- `orp_mv`
- `turbidity_ntu`

Estado:

- Requiere artefacto LSTM entrenado.
- La UI debe mostrar cobertura temporal por variable y alertar si faltan series o unidades.

### FISH_COUNTING_MODEL

Uso visual: conteo desde imagen/frame.

Formulario/media:

- `image` o `video_frame`
- `camera_calibration`

Estado:

- Requiere artefacto de vision entrenado.

### FISH_SIZE_WEIGHT_ESTIMATION

Uso visual: talla, peso y biomasa desde imagen/frame.

Formulario/media:

- `image` o `video_frame`
- `calibration_parameters`
- `species`

Estado:

- Requiere artefacto de vision entrenado.

## Rutas de gemelo, riesgos y recomendaciones

Para vista ejecutiva del estanque:

```text
GET /ponds/{pond_id}/state
POST /digital-twin/{pond_id}/snapshot
POST /digital-twin/{pond_id}/snapshots
GET /digital-twin/snapshots/{snapshot_id}
GET /digital-twin/{pond_id}/latest
GET /digital-twin/{pond_id}/risks
GET /digital-twin/{pond_id}/recommendations
GET /alerts?pond_id={pond_id}
GET /recommendations?pond_id={pond_id}
GET /twin/state/{pond_id}
POST /twin/prescription/recommend?pond_id={pond_id}
```

La UI debe permitir crear snapshot, ver riesgos y convertir recomendaciones en acciones.

## Rutas de actuacion

Para panel de equipos:

```text
GET /actuators?pond_id={pond_id}
GET /actuators/{actuator_id}
POST /actuators
POST /actuation-commands/from-recommendation
GET /actuation-commands
```

El frontend debe mostrar comandos como borradores o decisiones, no como ejecucion fisica automatica, salvo que se implemente una capa IoT posterior.

## Datos que conviene agregar a aquaculture_digital_twin

Sin tocar la base legacy, la nueva BD debe guardar o sincronizar estos datos para reducir formularios:

- Metadatos de estanque: volumen en litros y m3, area, geometria, tipo de sistema, flujo nominal.
- Hidraulica: caudal, recambio, aireacion, reaeracion, oxigenacion, bomba y eficiencia.
- Biomasa: conteo de peces, peso promedio, talla, biomasa total, densidad.
- Alimentacion: alimento ofrecido, alimento remanente, FCR, racion, tasa de crecimiento diaria.
- Dieta: proteina, lipidos, carbohidratos, digestibilidades, energia del tejido.
- Series de agua: pH, temperatura, oxigeno, amoniaco, nitrito, ORP, turbidez con unidades normalizadas.
- Operacion RAS: volumen, densidad, BOD5, ciclos de bomba y transferencia de oxigeno.
- Vision: referencias de imagen/frame, calibracion de camara, especie y artefactos entrenados.
- Model assets: pesos BPNN, LSTM y vision con version, fecha, metricas y estado activo.

Tablas propias usadas por el backend para esta UI:

- `farms`
- `ponds`
- `sensors`
- `raw_measurements`
- `clean_measurements`
- `digital_twin_snapshots`
- `model_outputs`
- `actuators`
- `actuation_commands`

La tabla legacy `sismapiscis` no debe recibir escrituras desde este backend. La sincronizacion solo lee y copia hacia `aquaculture_digital_twin` con IDs `LEGACY-*`.

`model_outputs` es la tabla de trazabilidad de ejecuciones. Cada `test-run`, `test-run-all` o ejecucion real guarda un `run_id`, `model_code`, salida JSON y fecha de creacion. La tabla de trazabilidad del frontend debe salir de ahi, no de memoria del navegador.

## Regla para que ningun formulario quede al aire

Cada campo visible debe venir de `input-audit.form_fields`.

El frontend debe guardar para cada campo:

- `input_name`
- `unit`
- `status`
- `control`
- `source`
- `value_preview`
- `options`
- `note`

El boton ejecutar solo se habilita cuando:

- todos los `missing_inputs` tienen valor de formulario;
- las unidades coinciden;
- `blocked_by` esta vacio, salvo que el usuario active `dry_run` o `metadata_only`.

## Prueba completa desde frontend

Para validar que el frontend consume el backend correctamente, debe ejecutar esta secuencia contra despliegue:

```text
GET /health
GET /models
GET /models/{model_code}/input-audit?pond_id={pond_id}
GET /models/{model_code}/test-payload?pond_id={pond_id}
POST /models/{model_code}/test-run?pond_id={pond_id}
POST /models/{model_code}/run
```

Uso esperado:

- `input-audit` arma el formulario real.
- `test-payload` completa automaticamente datos faltantes para probar el modelo.
- `test-run` confirma que la ruta, contrato, unidades y salida funcionan.
- `run` se usa cuando el usuario ya completo el formulario productivo.

El frontend debe mostrar una etiqueta visible cuando un input venga con:

```text
quality_flag = generated_test_value
```

Ese valor permite probar la pantalla y el contrato, pero no debe presentarse como dato medido.

Resultado minimo esperado por modelo:

- `status 200`;
- `model_code` igual al solicitado;
- `run_id` presente;
- `outputs` presente;
- si `readiness_status` es `requires_external_artifact`, deben mostrarse `warnings`.

Si un modelo falla en `test-run`, el frontend no debe ocultarlo: debe mostrar el error de backend y bloquear la ejecucion productiva hasta corregir inputs, unidades o artefacto.

## Grafico de datos

El grafico debe usar:

```text
GET /telemetry/timeseries?pond_id={pond_id}&variable_code={variable}&limit={n}
```

Debe permitir:

- selector de variable;
- rango o limite de puntos;
- unidad visible en eje Y;
- fecha/hora en eje X;
- ultimo valor destacado;
- aviso de datos incompletos si hay huecos;
- downsampling visual si hay demasiados puntos.

## Prioridad de implementacion visual

1. Operacion en vivo del estanque.
2. Catalogo de modelos con auditoria de inputs.
3. Ejecutor generico de modelos.
4. Panel de resultados y trazabilidad.
5. Snapshots, riesgos y recomendaciones.
6. Actuadores y comandos.
7. Carga/gestion de artefactos ML y vision.
