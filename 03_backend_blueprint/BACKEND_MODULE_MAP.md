# BACKEND_MODULE_MAP.md

## Módulos backend

### `farm_management`

Responsable de:

- granjas;
- estanques;
- canales;
- jaulas;
- sensores instalados;
- actuadores instalados;
- ciclos productivos;
- lotes de peces.

### `iot_ingestion`

Responsable de:

- HTTP ingestion;
- MQTT ingestion;
- CSV/Excel import;
- validación de payload;
- almacenamiento raw;
- normalización inicial.

### `data_quality`

Responsable de:

- validar rangos físicos;
- convertir unidades;
- detectar outliers;
- detectar sensor congelado;
- detectar huecos temporales;
- interpolar cuando esté permitido;
- generar `quality_flag`.

### `time_series_store`

Responsable de:

- guardar datos en TimescaleDB;
- consultar ventanas temporales;
- calcular agregados;
- alimentar modelos.

### `model_registry`

Responsable de:

- model_definition;
- model_version;
- model_source_reference;
- model_parameter_set;
- model_input_schema;
- model_output_schema;
- model_run.

### `dissolved_oxygen_models`

Implementa:

- `DO_DYNAMIC_0D_ROYER_2021`;
- `OXYGEN_CONSUMPTION_SINUSOIDAL`;
- `DO_MASS_BALANCE_RAS`.

### `ammonia_nitrogen_models`

Implementa:

- `AMMONIA_PREDICTIVE_MODEL`;
- TAN;
- amonio no ionizado;
- carga de nitrificación;
- riesgo tóxico.

### `bioenergetic_models`

Implementa:

- `BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010`;
- `INGESTION_OPTIMAL_MODEL`;
- `ASSIMILATION_DIET_MODEL`;
- `FECES_PRODUCTION_MODEL`;
- `FASTING_CATABOLISM_MODEL`.

### `feeding_models`

Implementa:

- `BPNN_MEA_FEED_INTAKE`;
- `FEEDING_SATIETY_RULES`;
- `DAILY_RATION_MODEL`;
- feed waste risk;
- feed recommendation.

### `water_quality_forecasting`

Implementa:

- `PEARSON_LSTM_ATTENTION_WQ`;
- preprocesamiento;
- selección Pearson;
- ventanas temporales;
- métricas ML.

### `computer_vision`

Implementa:

- conteo de peces;
- estimación de tamaño/peso/biomasa;
- comportamiento alimentario;
- vitalidad/mortalidad;
- detección de algas/redes.

### `digital_twin_engine`

Responsable de orquestar:

```text
estado actual
+ calidad de agua
+ biomasa
+ alimentación
+ OD
+ amonio
+ ML
+ visión
+ reglas
= snapshot del gemelo digital
```

### `decision_engine`

Responsable de:

- índice de riesgo;
- generación de recomendaciones;
- explicación;
- priorización;
- aprobación manual.

### `actuation`

Responsable de:

- comandos a comedero;
- aireador;
- bomba;
- válvula;
- alarmas;
- auditoría de ejecución.
