# Backend limpio para Gemelo Digital Acuícola

## Objetivo

Implementar un **backend Python limpio, corto, modular y completo** para un sistema experto de acuicultura basado en:

- Gemelo Digital.
- IoT.
- Oxígeno disuelto.
- Amoniaco/nitrificación.
- Modelos bioenergéticos.
- Alimentación inteligente.
- Machine Learning.
- Deep Learning.
- Visión artificial.
- Recomendaciones y actuación.

Este proyecto **no es un notebook**, **no es un dashboard**, **no es frontend** y **no debe convertirse en scripts sueltos**.  
Es un backend profesional que debe guardar datos, ejecutar modelos, registrar trazabilidad y exponer APIs limpias.

---

# 1. Regla principal

Cuando se diga **modelo**, no asumir que significa solo Machine Learning.

En este proyecto, un modelo puede ser:

- modelo matemático;
- modelo bioenergético;
- modelo de oxígeno disuelto;
- modelo de amoniaco;
- modelo de crecimiento;
- modelo de alimentación;
- modelo ML;
- modelo Deep Learning;
- modelo de visión artificial;
- modelo de decisión;
- modelo de base de datos;
- modelo de dominio backend.

Antes de implementar cualquier modelo, revisar siempre:

```text
01_CONTEXT_MASTER.md
02_MODEL_CATALOG.yaml
03_BACKEND_IMPLEMENTATION_RULES.md
04_CODEX_MASTER_PROMPT.md
backend_blueprint/
```

---

# 2. Restricciones obligatorias

```text
1. Backend puro.
2. No implementar frontend.
3. No implementar dashboards.
4. No usar notebooks como solución principal.
5. No crear scripts sueltos como arquitectura.
6. No meter lógica de modelos dentro de endpoints.
7. No meter SQL directo dentro de modelos científicos.
8. No inventar fórmulas faltantes.
9. Si una fórmula no está clara, usar FORMULA_PENDING_EXTRACTION.
10. Todo modelo debe tener model_code.
11. Todo modelo debe tener source_report.
12. Todo modelo debe tener inputs, outputs, units y assumptions.
13. Todo modelo debe registrar model_run.
14. Todo dato IoT debe guardarse como raw_measurement y clean_measurement.
15. Toda predicción debe guardar modelo, versión, parámetros, entradas y salida.
16. El Gemelo Digital orquesta modelos; no debe contener toda la lógica mezclada.
```

---

# 3. Stack recomendado

```text
Python 3.11+
FastAPI
Pydantic v2
SQLAlchemy 2
Alembic
PostgreSQL
TimescaleDB
Redis
Celery/RQ/Dramatiq
MLflow
MinIO/S3
NumPy
Pandas
SciPy
scikit-learn
PyTorch/TensorFlow
OpenCV
Pytest
```

---

# 4. Estructura limpia del backend

```text
backend/
  app/
    main.py

    core/
      config.py
      database.py
      security.py
      logging.py
      exceptions.py

    api/
      v1/
        health.py
        farms.py
        ponds.py
        sensors.py
        measurements.py
        models.py
        predictions.py
        digital_twin.py
        alerts.py
        actuation.py

    domains/
      farms/
      ponds/
      species/
      sensors/
      water_quality/
      biomass/
      feeding/
      vision/
      models/
      digital_twin/
      alerts/
      actuation/

    infrastructure/
      db/
      repositories/
      object_storage/
      queues/
      mqtt/
      mlflow/
      external_devices/

    models_engine/
      base/
        model_contract.py
        model_context.py
        model_result.py

      mechanistic/
        dissolved_oxygen_0d.py
        oxygen_mass_balance_ras.py
        ammonia_nitrification.py

      bioenergetic/
        growth_model.py
        ingestion_model.py
        assimilation_model.py
        feces_model.py
        catabolism_model.py

      ml/
        bpnn_mea_feed_intake.py
        pearson_lstm_attention.py
        preprocessing.py
        training_pipeline.py

      vision/
        fish_detection.py
        fish_counting.py
        fish_size_estimation.py
        feeding_behavior.py

      orchestrators/
        digital_twin_orchestrator.py
        scenario_simulator.py
        recommendation_engine.py

    workers/
      ingest_worker.py
      model_worker.py
      vision_worker.py
      alert_worker.py

    shared/
      enums.py
      units.py
      time.py
      validators.py

    tests/

  migrations/
  docs/
  scripts/
```

---

# 5. Orden correcto de implementación

## Fase 1: Arquitectura base

Implementar primero:

```text
FastAPI app
settings
database connection
SQLAlchemy base
Alembic
health endpoint
estructura modular
logging
exceptions
tests básicos
```

No implementar todavía modelos científicos.

---

## Fase 2: Base de datos

Crear entidades y migraciones para:

```text
granjas
estanques
canales
sensores
calibraciones de sensores
mediciones crudas
mediciones limpias
especies
lotes de peces
biomasa
mortalidad
alimentación
productos de alimento
composición del alimento
modelos
versiones de modelos
parámetros de modelos
ejecuciones de modelos
entradas de modelos
salidas de modelos
predicciones
alertas
recomendaciones
actuadores
comandos
auditoría
```

---

## Fase 3: Contrato común de modelos

Antes de programar OD, bioenergético, LSTM, BPNN o visión artificial, crear:

```text
BaseModelRunner
ModelInput
ModelOutput
ModelRunContext
ModelMetadata
ModelRegistryRepository
ModelRunRepository
```

Todo modelo debe implementar:

```text
validate_inputs()
preprocess()
predict()
postprocess()
explain()
save_run()
```

---

## Fase 4: Modelos individuales

Implementar de uno en uno, no todos juntos.

Orden sugerido:

```text
1. DO_DYNAMIC_0D_ROYER_2021
2. OXYGEN_CONSUMPTION_SINUSOIDAL
3. DO_MASS_BALANCE_RAS
4. AMMONIA_PREDICTIVE_MODEL
5. BIOENERGETIC_SPARUS_AURATA
6. DAILY_RATION_MODEL
7. BPNN_MEA_FEED_INTAKE
8. PEARSON_LSTM_ATTENTION_WQ
9. FISH_COUNTING_MODEL
10. FISH_SIZE_WEIGHT_ESTIMATION
```

---

## Fase 5: Gemelo Digital

Después de tener modelos individuales:

```text
digital_twin_orchestrator.py
scenario_simulator.py
recommendation_engine.py
risk_engine.py
```

El Gemelo Digital debe:

```text
1. cargar estado actual;
2. cargar sensores recientes;
3. cargar biomasa;
4. cargar alimentación;
5. ejecutar modelos;
6. fusionar resultados;
7. calcular riesgos;
8. generar recomendaciones;
9. guardar snapshot;
10. registrar trazabilidad.
```

---

# 6. Contrato mínimo de todo modelo

## Entrada

```json
{
  "model_code": "DO_DYNAMIC_0D_ROYER_2021",
  "pond_id": "POND-001",
  "timestamp": "2026-01-01T10:00:00Z",
  "inputs": {
    "dissolved_oxygen": {
      "value": 6.1,
      "unit": "mg/L"
    },
    "water_temperature": {
      "value": 18.5,
      "unit": "°C"
    },
    "fish_biomass": {
      "value": 120.0,
      "unit": "kg"
    }
  },
  "parameters": {
    "reaeration_rate": 0.046,
    "raceway_volume": 1280
  }
}
```

## Salida

```json
{
  "model_code": "DO_DYNAMIC_0D_ROYER_2021",
  "model_version": "1.0.0",
  "source_report": "Informe016",
  "prediction": {
    "variable": "dissolved_oxygen",
    "value": 5.82,
    "unit": "mg/L",
    "horizon_minutes": 60
  },
  "confidence": 0.78,
  "risk_level": "medium",
  "warnings": [
    "fish_biomass was estimated, not directly measured"
  ],
  "traceability": {
    "model_run_id": "RUN-000001",
    "parameter_set_id": "PARAM-001",
    "input_window_start": "2026-01-01T09:00:00Z",
    "input_window_end": "2026-01-01T10:00:00Z"
  }
}
```

---

# 7. Interfaz base sugerida

```python
from abc import ABC, abstractmethod
from typing import Any, Dict
from pydantic import BaseModel, Field


class ModelRunContext(BaseModel):
    model_code: str
    model_version: str
    source_report: str
    pond_id: str
    timestamp: str
    parameter_set_id: str | None = None


class ModelResult(BaseModel):
    model_code: str
    model_version: str
    source_report: str
    outputs: Dict[str, Any]
    units: Dict[str, str]
    confidence: float | None = None
    warnings: list[str] = Field(default_factory=list)
    explainability: Dict[str, Any] = Field(default_factory=dict)


class BaseModelRunner(ABC):
    model_code: str
    model_version: str
    source_report: str

    @abstractmethod
    def validate_inputs(self, inputs: Dict[str, Any]) -> None:
        pass

    def preprocess(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return inputs

    @abstractmethod
    def predict(self, inputs: Dict[str, Any], context: ModelRunContext) -> ModelResult:
        pass

    def postprocess(self, result: ModelResult) -> ModelResult:
        return result

    def explain(self, result: ModelResult) -> Dict[str, Any]:
        return result.explainability

    def run(self, inputs: Dict[str, Any], context: ModelRunContext) -> ModelResult:
        self.validate_inputs(inputs)
        clean_inputs = self.preprocess(inputs)
        result = self.predict(clean_inputs, context)
        return self.postprocess(result)
```

---

# 8. Endpoints mínimos

```text
GET  /api/v1/health

POST /api/v1/measurements/ingest
GET  /api/v1/ponds/{pond_id}/state
GET  /api/v1/ponds/{pond_id}/timeseries

GET  /api/v1/models
POST /api/v1/models/{model_code}/run
GET  /api/v1/models/runs/{run_id}

POST /api/v1/digital-twin/{pond_id}/snapshot
POST /api/v1/digital-twin/{pond_id}/simulate
GET  /api/v1/digital-twin/{pond_id}/recommendations

POST /api/v1/vision/infer

GET  /api/v1/alerts
POST /api/v1/actuators/{actuator_id}/command
```

---

# 9. Reglas de datos

## Datos crudos

Guardar exactamente lo recibido:

```text
sensor_measurement_raw
```

Campos:

```text
id
timestamp
farm_id
pond_id
sensor_id
variable
raw_value
raw_unit
raw_payload
source_type
received_at
```

## Datos limpios

Guardar el dato validado y normalizado:

```text
sensor_measurement_clean
```

Campos:

```text
id
raw_measurement_id
timestamp
farm_id
pond_id
sensor_id
variable
clean_value
standard_unit
quality_flag
validation_status
cleaning_method
created_at
```

Nunca borrar el dato crudo.

---

# 10. Model Registry

Debe existir un catálogo interno de modelos.

Tablas mínimas:

```text
model_definition
model_version
model_source_reference
model_parameter_set
model_input_schema
model_output_schema
model_run
model_run_input
model_run_output
model_validation_metric
```

Cada ejecución debe guardar:

```text
model_code
model_version
source_report
parameter_set_id
inputs
outputs
warnings
confidence
created_at
```

---

# 11. Módulos científicos mínimos

## Oxígeno disuelto

```text
DO_DYNAMIC_0D_ROYER_2021
OXYGEN_CONSUMPTION_SINUSOIDAL
DO_MASS_BALANCE_RAS
```

## Amoniaco

```text
AMMONIA_PREDICTIVE_MODEL
NITRIFICATION_LOAD_MODEL
UNIONIZED_AMMONIA_RISK_MODEL
```

## Bioenergético

```text
BIOENERGETIC_SPARUS_AURATA
INGESTION_OPTIMAL_MODEL
ASSIMILATION_MODEL
FECES_PRODUCTION_MODEL
FASTING_CATABOLISM_MODEL
```

## Alimentación

```text
BPNN_MEA_FEED_INTAKE
DAILY_RATION_MODEL
FEEDING_SATIETY_RULES
FEED_WASTE_MODEL
```

## Calidad de agua

```text
PEARSON_LSTM_ATTENTION_WQ
WATER_QUALITY_RISK_MODEL
```

## Visión artificial

```text
FISH_COUNTING_MODEL
FISH_SIZE_WEIGHT_ESTIMATION
FISH_HEALTH_BEHAVIOR_MODEL
MORTALITY_DETECTION_MODEL
```

## Gemelo Digital

```text
DT_DESCRIPTIVE_STATE
DT_DIAGNOSTIC
DT_PREDICTIVE
DT_PRESCRIPTIVE
DT_ACTUATION
```

---

# 12. Checklist para aceptar código

Aceptar solo si cumple:

```text
[ ] Tiene estructura modular.
[ ] Usa FastAPI limpio.
[ ] Usa SQLAlchemy y Alembic.
[ ] No hay app.py gigante.
[ ] No hay SQL directo dentro de modelos científicos.
[ ] No hay lógica científica dentro de endpoints.
[ ] Hay raw_measurement y clean_measurement.
[ ] Hay model_registry.
[ ] Hay model_run.
[ ] Cada modelo tiene model_code.
[ ] Cada modelo tiene source_report.
[ ] Cada salida tiene unidades.
[ ] Las fórmulas dudosas están como FORMULA_PENDING_EXTRACTION.
[ ] Hay tests básicos.
[ ] El Gemelo Digital orquesta y no mezcla todo.
[ ] No hay frontend.
[ ] No hay dashboard.
[ ] No hay notebook como solución principal.
```

---

# 13. Prompt corto para Codex

```text
Implementa este proyecto como backend Python profesional, limpio y modular.

Lee primero:
- 01_CONTEXT_MASTER.md
- 02_MODEL_CATALOG.yaml
- 03_BACKEND_IMPLEMENTATION_RULES.md
- 04_CODEX_MASTER_PROMPT.md
- backend_blueprint/

Restricciones:
- backend puro;
- no frontend;
- no dashboards;
- no notebooks como arquitectura;
- no scripts sueltos;
- no lógica de modelos en endpoints;
- no SQL dentro de modelos científicos;
- no inventar fórmulas;
- usar FORMULA_PENDING_EXTRACTION si falta una fórmula;
- todo modelo debe tener model_code, source_report, inputs, outputs, units, assumptions y model_run;
- todo dato IoT debe tener raw_measurement y clean_measurement;
- toda predicción debe guardar trazabilidad;
- el Gemelo Digital solo orquesta.

Primero implementa solo la arquitectura base:
FastAPI, settings, database, SQLAlchemy base, Alembic, estructura modular, health endpoint y tests básicos.

No implementes todavía modelos científicos.
Cuando termines, detente y explica qué archivos creaste.
```

---

# 14. Prompt para implementar un modelo específico

```text
Implementa solo el modelo DO_DYNAMIC_0D_ROYER_2021.

Antes de programar:
1. Lee 02_MODEL_CATALOG.yaml.
2. Verifica inputs, outputs, unidades, source_report y supuestos.
3. Usa BaseModelRunner.
4. No consultes la base de datos dentro del modelo.
5. No inventes fórmulas.
6. Si una fórmula está incompleta, usa FORMULA_PENDING_EXTRACTION.
7. Devuelve ModelResult.
8. Registra model_run mediante el servicio correspondiente.
9. Agrega tests unitarios.

No modifiques frontend.
No crees notebooks.
No mezcles este modelo con otros modelos.
```

---

# 15. Resultado esperado

El backend debe poder responder:

```text
¿Cuál es el estado actual del estanque?
¿Cuánto OD habrá en 1, 3, 6 y 24 horas?
¿Cuánto alimento debo dar hoy?
¿Hay riesgo de hipoxia?
¿Hay riesgo de amoniaco?
¿Cuál será la biomasa futura?
¿Qué modelo generó esta predicción?
¿Qué informe/paper respalda este modelo?
¿Qué datos usó?
¿Qué versión de parámetros usó?
¿Qué recomendación operativa corresponde?
```

---

# 16. Regla final

Primero plataforma backend.  
Después modelos.  
Después Gemelo Digital.  
Después recomendaciones.  
Después actuadores.

No empezar por `train.py`, `predict.py`, `notebook.ipynb` ni `app.py` gigante.
