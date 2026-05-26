# FRONTEND_MLOPS_EXECUTION_GUIDE.md

## Diagnostico directo del frontend actual

En este repositorio local no existe una carpeta de frontend disponible para auditar componentes reales. No se encontro `acuicola-frontend` ni codigo React/Vite/Next asociado.

Por lo tanto, el frontend actual no puede darse por validado para:

- conectar con la data real que se va a limpiar;
- mostrar modulo de limpieza;
- ejecutar tecnicas de limpieza;
- guardar o consultar corridas de limpieza;
- crear feature sets;
- preparar entrenamiento;
- lanzar training jobs;
- ver eventos de entrenamiento;
- activar artefactos;
- usar un modelo entrenado;
- ejecutar prediccion ML con artefacto activo.

Este documento define exactamente lo que el frontend debe implementar para consumir el backend como una plataforma MLOps acuicola completa.

Base API:

```text
http://37.60.226.53:8000/api/v1
```

En local:

```text
http://127.0.0.1:8000/api/v1
```

## Principio obligatorio

El frontend no debe ser una coleccion de formularios. Debe ser una consola de ciclo de vida ML:

```text
Datos -> Limpieza -> Feature set -> Entrenamiento -> Artefacto -> Activacion -> Prediccion -> Trazabilidad
```

Los formularios solo aparecen cuando falta un parametro. El backend ya expone rutas para guiar todos los estados.

## Navegacion minima requerida

El menu lateral debe tener estos modulos:

1. Resumen
2. Datos
3. Limpieza
4. Features
5. Entrenamiento
6. Artefactos
7. Modelos e inferencia
8. Trazabilidad

No ocultar los modulos MLOps dentro de "Modelos"; deben ser pantallas propias.

## 1. Resumen

Objetivo: mostrar estado general del backend, estanque activo, modelos, evidencia y ciclo ML.

Ruta:

```http
GET /frontend/dashboard?farm_id={farm_id}&pond_id={pond_id}
```

Debe mostrar:

- backend online/offline;
- granja seleccionada;
- estanque seleccionado;
- cantidad de sensores;
- variables disponibles;
- total de modelos;
- total de componentes;
- total de feature sets;
- total de training jobs;
- total de model assets;
- activos disponibles.

Campos a usar:

```text
backend.status
farms
ponds
system_metrics
component_summary
model_summary
ml_lifecycle
evidence.feature_sets
evidence.training_jobs
evidence.model_assets
frontend_contract_routes
```

Prueba frontend:

```text
1. Abrir Resumen.
2. Ver "Backend ONLINE".
3. Ver rutas MLOps dentro de frontend_contract_routes.
4. Confirmar que aparecen datasets, cleaning_runs, features, training_jobs y model_assets.
```

Prueba API:

```bash
curl http://127.0.0.1:8000/api/v1/frontend/dashboard
```

Resultado esperado:

```json
{
  "backend": {"status": "online"},
  "ml_lifecycle": {
    "datasets_enabled": true,
    "cleaning_enabled": true,
    "features_enabled": true,
    "training_enabled": true,
    "model_assets_enabled": true
  }
}
```

## 2. Datos

Objetivo: conectar el frontend con la data que se va a limpiar y entrenar.

Rutas:

```http
GET /datasets/sources
POST /datasets/sync-legacy
GET /datasets/coverage?pond_id={pond_id}
GET /datasets/readiness?pond_id={pond_id}&model_code={model_code}
GET /datasets/variables?pond_id={pond_id}
GET /datasets/timeseries?pond_id={pond_id}&variable_code={variable_code}
```

Vista requerida:

- selector de granja;
- selector de estanque;
- boton "Sincronizar legacy";
- tabla de variables;
- registros por variable;
- unidad;
- primera fecha;
- ultima fecha;
- completitud;
- si es entrenable;
- advertencias.

Columnas de tabla:

```text
variable_code
unit
records
first_time
last_time
missing_count
outlier_count
completeness_ratio
trainable
```

Ejemplo de sincronizacion:

```http
POST /datasets/sync-legacy
```

Respuesta esperada:

```json
{
  "status": "completed",
  "source": "legacy_mysql_sismapiscis"
}
```

Ejemplo de cobertura:

```http
GET /datasets/coverage?pond_id=LEGACY-POND-1
```

Respuesta esperada:

```json
{
  "pond_id": "LEGACY-POND-1",
  "total_records": 12000,
  "trainable_variables": [
    "water_temperature_c",
    "ph",
    "dissolved_oxygen_mg_l"
  ],
  "variables": [
    {
      "variable_code": "water_temperature_c",
      "records": 3000,
      "unit": "degC",
      "trainable": true
    }
  ]
}
```

Prueba frontend:

```text
1. Entrar a Datos.
2. Seleccionar estanque.
3. Click en "Sincronizar legacy".
4. Ver tabla de variables.
5. Elegir un modelo ML.
6. Ver si el dataset esta listo o faltan variables.
```

Bloqueo visual:

- Si `can_train=false`, deshabilitar "Crear feature set".
- Mostrar `missing_variables`.

## 3. Limpieza

Objetivo: ejecutar limpieza real de datos desde frontend.

Rutas:

```http
POST /data/cleaning-runs
GET /data/cleaning-runs
GET /data/cleaning-runs/{run_id}
GET /data/cleaning-runs/{run_id}/summary
GET /data/cleaning-runs/{run_id}/preview
```

Controles requeridos:

- selector de estanque;
- multiselect de variables;
- checkbox `apply_interpolation`;
- checkbox `apply_sigma3`;
- checkbox `apply_minmax`;
- checkbox `overwrite_clean_measurements`;
- boton "Ejecutar limpieza";
- tabla de runs;
- panel resumen;
- preview de registros limpios.

Payload:

```json
{
  "pond_id": "LEGACY-POND-1",
  "variable_codes": [
    "water_temperature_c",
    "ph",
    "dissolved_oxygen_mg_l"
  ],
  "apply_interpolation": true,
  "apply_sigma3": true,
  "apply_minmax": false,
  "overwrite_clean_measurements": false
}
```

Respuesta:

```json
{
  "run_id": "CLEANRUN-...",
  "status": "completed",
  "records_in": 3000,
  "records_out": 3000,
  "interpolated_points": 12,
  "outliers_detected": 4,
  "normalized_points": 0,
  "steps": [
    {
      "step_name": "interpolation",
      "status": "completed"
    },
    {
      "step_name": "sigma3",
      "status": "completed"
    }
  ]
}
```

Campos especificos que debe mostrar/guardar la UI:

```text
run_id
pond_id
variable_codes
status
records_in
records_out
interpolated_points
outliers_detected
normalized_points
started_at
finished_at
steps
```

Preview:

```http
GET /data/cleaning-runs/{run_id}/preview
```

Debe renderizar:

```text
time
variable_code
clean_value
standard_unit
quality_flag
validation_status
cleaning_method
```

Prueba frontend:

```text
1. Entrar a Limpieza.
2. Seleccionar estanque.
3. Seleccionar variables.
4. Activar interpolacion y 3-sigma.
5. Ejecutar.
6. Ver run completed.
7. Ver preview.
8. Ver quality_flag y cleaning_method por fila.
```

Si esta pantalla no existe, el frontend no cumple la arquitectura MLOps.

## 4. Features

Objetivo: preparar matrices para entrenar modelos.

Rutas:

```http
POST /features/build
GET /features
GET /features/{feature_set_id}
GET /features/{feature_set_id}/preview
GET /features/{feature_set_id}/columns
```

Controles requeridos:

- selector de estanque;
- selector de `cleaning_run_id`;
- selector de `target_variable`;
- multiselect de `feature_variables`;
- input `window_size`;
- input `horizon`;
- input `pearson_threshold`;
- input `train_fraction`;
- input `validation_fraction`;
- boton "Crear feature set".

Payload tabular:

```json
{
  "pond_id": "LEGACY-POND-1",
  "cleaning_run_id": "CLEANRUN-123",
  "target_variable": "dissolved_oxygen_mg_l",
  "feature_variables": [
    "water_temperature_c",
    "ph",
    "nitrate_ion"
  ],
  "window_size": 1,
  "horizon": 1,
  "pearson_threshold": null,
  "train_fraction": 0.7,
  "validation_fraction": 0.15
}
```

Payload secuencial:

```json
{
  "pond_id": "LEGACY-POND-1",
  "cleaning_run_id": "CLEANRUN-123",
  "target_variable": "dissolved_oxygen_mg_l",
  "feature_variables": [
    "water_temperature_c",
    "ph",
    "nitrate_ion"
  ],
  "window_size": 8,
  "horizon": 1,
  "pearson_threshold": 0.2,
  "train_fraction": 0.7,
  "validation_fraction": 0.15
}
```

Respuesta:

```json
{
  "feature_set_id": "FEATURESET-...",
  "pond_id": "LEGACY-POND-1",
  "target_variable": "dissolved_oxygen_mg_l",
  "rows_count": 1000,
  "train_rows": 700,
  "validation_rows": 150,
  "test_rows": 150,
  "columns": [
    {
      "name": "water_temperature_c",
      "role": "feature",
      "source_variable": "water_temperature_c",
      "pearson_score": -0.67
    },
    {
      "name": "target",
      "role": "target",
      "source_variable": "dissolved_oxygen_mg_l"
    }
  ]
}
```

Prueba frontend:

```text
1. Entrar a Features.
2. Seleccionar cleaning run.
3. Elegir target.
4. Elegir predictoras.
5. Crear feature set.
6. Ver train/validation/test.
7. Ver columnas y Pearson.
8. Ver preview de filas.
```

Bloqueo visual:

- Si no hay `cleaning_run_id`, permitir crear con clean actual, pero mostrar advertencia.
- Si `rows_count` es bajo, bloquear entrenamiento.

## 5. Entrenamiento

Objetivo: lanzar entrenamiento desde el frontend, sin notebooks ni scripts.

Rutas:

```http
GET /ml/lifecycle/status
GET /ml/trainable-models
POST /ml/training-jobs
POST /models/{model_code}/train
GET /ml/training-jobs
GET /ml/training-jobs/{job_id}
GET /ml/training-jobs/{job_id}/events
POST /ml/training-jobs/{job_id}/cancel
```

Vista requerida:

- lista de modelos entrenables;
- estado por modelo;
- variables requeridas;
- feature set seleccionado;
- hiperparametros;
- boton "Entrenar";
- estado del job;
- eventos/logs;
- metricas al finalizar.

Payload:

```json
{
  "model_code": "ML_SUPERVISED_LINEAR_REG",
  "feature_set_id": "FEATURESET-123",
  "hyperparameters": {
    "learning_rate": 0.0001,
    "epochs": 400
  },
  "auto_activate": true
}
```

Respuesta:

```json
{
  "job_id": "TRAINJOB-...",
  "model_code": "ML_SUPERVISED_LINEAR_REG",
  "feature_set_id": "FEATURESET-123",
  "status": "completed",
  "metrics": {
    "mse": 0.12,
    "rmse": 0.34,
    "mae": 0.21,
    "r2": 0.91
  },
  "asset_id": "ASSET-..."
}
```

Eventos:

```http
GET /ml/training-jobs/{job_id}/events
```

Respuesta:

```json
[
  {
    "event_type": "queued",
    "message": "Training job created."
  },
  {
    "event_type": "running",
    "message": "Training pipeline started."
  },
  {
    "event_type": "completed",
    "message": "Training completed and model asset registered."
  }
]
```

Prueba frontend:

```text
1. Entrar a Entrenamiento.
2. Ver modelos desde /ml/trainable-models.
3. Seleccionar feature set.
4. Ajustar hyperparameters.
5. Ejecutar training job.
6. Ver estado queued/running/completed.
7. Ver metricas.
8. Ver asset_id generado.
```

Estados visuales:

```text
queued       -> gris
running      -> azul
completed    -> verde
failed       -> rojo
cancelled    -> amarillo
```

## 6. Artefactos

Objetivo: administrar versiones entrenadas.

Rutas:

```http
GET /ml/model-assets
GET /ml/model-assets?model_code={model_code}
GET /ml/model-assets?status=active
GET /ml/model-assets/{asset_id}
POST /ml/model-assets/{asset_id}/activate
POST /ml/model-assets/{asset_id}/deprecate
GET /models/{model_code}/asset
GET /models/{model_code}/metrics
```

Vista requerida:

- tabla por modelo;
- version;
- estado;
- metricas;
- fecha de creacion;
- fecha de activacion;
- boton "Activar";
- boton "Deprecar".

Campos:

```text
asset_id
model_code
version
artifact_path
artifact_format
feature_set_id
training_job_id
metrics_json
status
created_at
activated_at
deprecated_at
```

Prueba frontend:

```text
1. Entrar a Artefactos.
2. Ver assets creados.
3. Activar un asset candidate.
4. Ver que pasa a active.
5. Consultar /models/{model_code}/asset.
6. Ver metricas activas.
```

## 7. Inferencia ML

Objetivo: usar modelos entrenados desde frontend.

Rutas:

```http
POST /models/{model_code}/predict
POST /ml/model-assets/{asset_id}/predict
```

Antes de predecir:

```http
GET /models/{model_code}/asset
```

Si no hay asset activo, bloquear boton "Predecir" y mostrar "Entrene o active un artefacto".

Payload:

```json
{
  "features": {
    "water_temperature_c": 27.0,
    "ph": 7.6,
    "nitrate_ion": 0.15
  }
}
```

Respuesta:

```json
{
  "model_code": "ML_SUPERVISED_LINEAR_REG",
  "asset_id": "ASSET-123",
  "version": "v1",
  "prediction": 6.31,
  "feature_names": [
    "water_temperature_c",
    "ph",
    "nitrate_ion"
  ],
  "traceability": {
    "artifact_path": "model_assets/ML_SUPERVISED_LINEAR_REG/v1.json",
    "feature_set_id": "FEATURESET-123",
    "training_job_id": "TRAINJOB-123",
    "artifact_status": "active"
  }
}
```

Prueba frontend:

```text
1. Ir a Inferencia.
2. Elegir modelo.
3. Confirmar asset activo.
4. Renderizar inputs segun feature_names del asset.
5. Enviar features.
6. Mostrar prediction.
7. Mostrar traceability.
```

## 8. Modelos deterministas y runners existentes

Estos no necesitan training job para funcionar.

Rutas:

```http
GET /models
GET /models/{model_code}/input-audit?pond_id={pond_id}
GET /models/{model_code}/test-payload?pond_id={pond_id}
POST /models/{model_code}/test-run?pond_id={pond_id}
POST /models/{model_code}/run
POST /models/test-run-all?pond_id={pond_id}
```

Regla frontend:

- usar `input-audit` para construir el formulario;
- usar `test-payload` para demo;
- usar `test-run` para validar contrato;
- usar `run` para ejecucion productiva.

Prueba:

```text
1. Abrir catalogo.
2. Seleccionar DO_DYNAMIC_0D_ROYER_2021.
3. Cargar input-audit.
4. Ver campos automaticos y requeridos.
5. Ejecutar test-run.
6. Mostrar outputs y warnings.
```

## 9. Trazabilidad

Objetivo: que el usuario vea que ejecucion, modelo, version y datos se usaron.

Fuentes:

```http
GET /frontend/dashboard
GET /ml/training-jobs/{job_id}
GET /ml/training-jobs/{job_id}/events
GET /ml/model-assets/{asset_id}
GET /models/{model_code}/metrics
```

Debe mostrar:

- `run_id` para runners;
- `job_id` para entrenamientos;
- `asset_id` para modelos entrenados;
- `feature_set_id`;
- `training_job_id`;
- metricas;
- version;
- fecha.

## 10. Prueba end-to-end que el frontend debe pasar

El frontend se considera listo solo si puede ejecutar esta secuencia completa:

```text
1. GET /health
2. GET /farms
3. GET /ponds
4. POST /datasets/sync-legacy
5. GET /datasets/coverage?pond_id={pond_id}
6. GET /datasets/readiness?pond_id={pond_id}&model_code=ML_SUPERVISED_LINEAR_REG
7. POST /data/cleaning-runs
8. GET /data/cleaning-runs/{run_id}/preview
9. POST /features/build
10. GET /features/{feature_set_id}/preview
11. POST /ml/training-jobs
12. GET /ml/training-jobs/{job_id}/events
13. GET /ml/model-assets/{asset_id}
14. POST /ml/model-assets/{asset_id}/activate
15. POST /models/ML_SUPERVISED_LINEAR_REG/predict
16. Mostrar prediction y traceability
```

Si cualquiera de esos pasos no tiene pantalla, boton, estado visual o manejo de error, el frontend no cumple.

## 11. Manejo de errores obligatorio

### Dataset insuficiente

Endpoint:

```http
GET /datasets/readiness
```

Si:

```json
{
  "can_train": false,
  "missing_variables": ["nitrate_ion"]
}
```

Mostrar:

```text
No se puede entrenar: faltan variables o registros.
```

### Limpieza sin datos

Si `POST /data/cleaning-runs` devuelve error, mostrar:

```text
No hay datos crudos suficientes para limpiar.
```

### Feature set vacio

Si `rows_count=0`, bloquear entrenamiento.

### Training failed

Si:

```json
{
  "status": "failed",
  "error_message": "..."
}
```

Mostrar error y link al detalle de eventos.

### Sin asset activo

Si:

```http
GET /models/{model_code}/asset
```

devuelve `null`, bloquear prediccion.

## 12. Checklist de implementacion frontend

- [ ] Configurar `API_BASE_URL`.
- [ ] Crear cliente API unico.
- [ ] Implementar pantalla Resumen.
- [ ] Implementar pantalla Datos.
- [ ] Implementar boton Sync Legacy.
- [ ] Implementar tabla Coverage.
- [ ] Implementar Dataset Readiness por modelo.
- [ ] Implementar pantalla Limpieza.
- [ ] Implementar formulario de Cleaning Run.
- [ ] Implementar preview de limpieza.
- [ ] Implementar pantalla Features.
- [ ] Implementar builder de Feature Set.
- [ ] Implementar preview de Feature Set.
- [ ] Implementar pantalla Entrenamiento.
- [ ] Implementar Training Jobs.
- [ ] Implementar eventos de Training Job.
- [ ] Implementar pantalla Artefactos.
- [ ] Implementar activar/deprecar asset.
- [ ] Implementar pantalla Inferencia ML.
- [ ] Implementar `/models/{model_code}/predict`.
- [ ] Implementar catalogo de runners deterministas.
- [ ] Implementar input-audit dinamico.
- [ ] Implementar test-run.
- [ ] Implementar visualizacion de trazabilidad.
- [ ] Implementar estados de error.

## 13. Orden recomendado de desarrollo

1. Cliente API y variables de entorno.
2. Resumen conectado a `/frontend/dashboard`.
3. Datos conectado a `/datasets/coverage`.
4. Limpieza conectado a `/data/cleaning-runs`.
5. Features conectado a `/features/build`.
6. Entrenamiento conectado a `/ml/training-jobs`.
7. Artefactos conectado a `/ml/model-assets`.
8. Inferencia conectado a `/models/{model_code}/predict`.
9. Modelos deterministas conectado a `/models`.
10. Trazabilidad y errores.

## 14. Criterio de aceptacion final

El frontend queda aceptado si una persona puede, sin tocar codigo:

1. elegir un estanque;
2. ver la data real disponible;
3. limpiar esa data;
4. ver que tecnica se aplico;
5. crear un feature set;
6. entrenar un modelo;
7. ver metricas;
8. activar un artefacto;
9. predecir con ese artefacto;
10. ver trazabilidad de todo el ciclo.

Ese es el minimo para que el frontend use realmente el backend ML.
