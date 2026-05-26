# Diagnostico local y plan maestro MLOps para AquaTwin Studio

## Veredicto ejecutivo

El backend actual ya sirve como API de gemelo digital y puede ejecutar simulaciones, pruebas de contrato y modelos deterministas. En la integracion local actual se habilito el primer ciclo de vida ML completo para datos tabulares: diagnostico de datasets, limpieza auditable, feature sets, training jobs, model assets, activacion de artefactos y metricas.

El problema no es que falten formularios. El problema real es que faltan servicios backend para:

- diagnosticar datasets;
- limpiar datos historicos de forma auditable;
- construir feature sets;
- lanzar entrenamientos;
- registrar artefactos/versiones;
- activar modelos;
- usar artefactos activos para inferencia real tabular;
- monitorear desempeno y reentrenar.

Los formularios solo deben capturar parametros faltantes. No deben ser el centro del sistema. El centro debe ser el ciclo de vida de modelos.

## Diagnostico contra la imagen objetivo

### 1. Fuentes de datos

Estado: habilitado localmente, pendiente de validacion en VPS.

Existe:

- Lectura desde la base legacy `sismapiscis`.
- Sincronizacion no destructiva hacia la base propia.
- Ingesta API de mediciones nuevas.
- Variables reales: temperatura, pH, oxigeno disuelto y nitrato desde legacy.

Falta para endurecer:

- Inventario formal de fuentes.
- Cobertura por variable, estanque y rango temporal.
- Registro operativo de alimentacion, biomasa y eventos como datasets entrenables.
- Validacion de si una fuente alcanza para entrenar un modelo especifico.

Rutas existentes relacionadas:

- `POST /measurements/ingest`
- `GET /measurements/raw`
- `GET /measurements/clean`
- `GET /ponds/{pond_id}/timeseries`
- `GET /telemetry/raw`
- `GET /telemetry/clean`
- `GET /telemetry/timeseries`

Rutas necesarias:

- `GET /datasets/sources`
- `POST /datasets/sync-legacy`
- `GET /datasets/coverage?pond_id={pond_id}`
- `GET /datasets/readiness?pond_id={pond_id}&model_code={model_code}`
- `GET /datasets/variables?pond_id={pond_id}`

### 2. Persistencia relacional MySQL

Estado: habilitado localmente para tablas runtime MLOps, pendiente de migracion formal/Alembic.

Existe:

- MySQL como base operativa.
- Tablas runtime propias: `farms`, `ponds`, `sensors`, `raw_measurements`, `clean_measurements`, `model_outputs`, `digital_twin_snapshots`, `actuators`, `actuation_commands`.
- Metadata SQLAlchemy para `models.model_definition`, `models.model_version`, `models.model_run`, `models.model_run_input`, `models.model_run_output`.

Falta para endurecer:

- Unificar la trazabilidad runtime con las tablas formales de modelos.
- Tablas MLOps reales para datasets, limpieza, features, entrenamientos y artefactos.
- Tabla runtime `model_assets`.
- Versionamiento de artefactos y estado activo/deprecado.

Tablas necesarias en `aquaculture_digital_twin`:

- `dataset_snapshots`
- `dataset_variable_coverage`
- `cleaning_runs`
- `cleaning_run_steps`
- `feature_sets`
- `feature_set_columns`
- `feature_set_rows`
- `training_jobs`
- `training_job_events`
- `model_assets`
- `model_asset_metrics`
- `model_inference_events`

Regla obligatoria:

- La base legacy `sismapiscis` queda solo lectura.
- Todo lo nuevo se escribe solo en `aquaculture_digital_twin`.

### 3. Bus de calidad e ingenieria de datos

Estado: habilitado localmente.

Existe como funciones:

- Interpolacion lineal.
- Regla 3-sigma.
- Normalizacion Min-Max.
- Correlacion Pearson.
- Ventanas temporales.
- Split temporal train/validation/test.
- Metricas de regresion y clasificacion.

Implementado como producto backend:

- Endpoint para ejecutar limpieza.
- Persistencia de cada corrida de limpieza.
- Vista previa despues de limpieza.
- Registro de outliers y vacios imputados.
- Feature sets persistentes reutilizables por entrenamiento.
- Contrato frontend para construir features sin inventar logica visual.

Rutas necesarias:

- `POST /data/cleaning-runs`
- `GET /data/cleaning-runs/{run_id}`
- `GET /data/cleaning-runs/{run_id}/summary`
- `GET /data/cleaning-runs/{run_id}/preview`
- `POST /features/build`
- `GET /features/{feature_set_id}`
- `GET /features/{feature_set_id}/preview`
- `GET /features/{feature_set_id}/columns`

Resultado esperado:

- El frontend debe poder mostrar "Limpiar dataset", "Ver outliers", "Ver interpolados", "Crear feature set", "Usar para entrenamiento".

### 4. Contenedor informatico web backend

Estado: parcial alto con ciclo MLOps inicial integrado.

Existe:

- FastAPI.
- Docker.
- API versionada.
- Catalogo de modelos.
- Runners deterministas y algunos modelos con artifact pending.
- Orquestador de gemelo digital.
- `test-payload`, `test-run` y `test-run-all`.

Implementado localmente:

- Jobs de entrenamiento sincronos de corta duracion.
- Registro de metricas de entrenamiento.
- Artefactos JSON versionados.
- Activacion/deprecacion de artefactos.

Falta para produccion:

- Worker asincrono para entrenamientos largos.
- Exportacion `.pkl`, `.joblib`, `.pt` u `.onnx`.
- Desbloqueo automatico de runners ML actuales con artefacto activo.
- Monitoreo de drift y reentrenamiento.

Rutas existentes:

- `GET /models`
- `GET /models/{model_code}`
- `GET /models/{model_code}/input-audit`
- `GET /models/{model_code}/test-payload`
- `POST /models/{model_code}/test-run`
- `POST /models/{model_code}/run`
- `POST /models/test-run-all`
- `GET /frontend/components`
- `GET /frontend/dashboard`

Rutas necesarias:

- `GET /ml/lifecycle/status`
- `GET /ml/trainable-models`
- `POST /models/{model_code}/train`
- `POST /ml/training-jobs`
- `GET /ml/training-jobs/{job_id}`
- `GET /ml/training-jobs/{job_id}/events`
- `POST /ml/training-jobs/{job_id}/cancel`
- `GET /ml/model-assets`
- `GET /ml/model-assets/{asset_id}`
- `POST /ml/model-assets/{asset_id}/activate`
- `POST /ml/model-assets/{asset_id}/deprecate`
- `GET /models/{model_code}/asset`
- `GET /models/{model_code}/metrics`
- `POST /ml/model-assets/{asset_id}/predict`
- `POST /models/{model_code}/predict`

### 5. API dinamica y UI guiada por datos

Estado: integrado para rutas MLOps y dashboard.

Existe:

- El frontend puede conocer catalogo, inputs, payload de prueba y estado de ejecucion.
- Los formularios pueden salir de `input-audit`.
- Hay dashboard agregado para frontend.

Implementado:

- Contrato visual para datasets, limpieza, features, entrenamiento y artefactos.
- Estados de ciclo de vida ML por modelo.
- Acciones backend claras para entrenar, activar y comparar.
- Inferencia tabular desde artefacto activo.

Falta:

- Reentrenamiento programado.
- Comparacion avanzada de versiones.

Estados necesarios por modelo:

- `not_trainable`
- `dataset_missing`
- `dataset_ready`
- `cleaning_required`
- `feature_set_ready`
- `training_available`
- `training_running`
- `trained_pending_activation`
- `active`
- `degraded`
- `retraining_required`
- `external_data_required`

El frontend no debe inventar estos estados. Debe leerlos desde:

- `GET /ml/lifecycle/status`
- `GET /ml/trainable-models`
- `GET /datasets/readiness`
- `GET /ml/model-assets`

### 6. Gobernanza MLOps

Estado: habilitado localmente en version inicial.

Existe ahora:

- `artifact_uri` en metadata SQLAlchemy de `ModelVersion`.
- Modelos que reconocen `requires_external_artifact`.
- `model_outputs` para persistir salidas simples.
- `model_assets` runtime.
- Registro de jobs.
- Version activa por modelo.
- Metricas por artefacto.
- Activacion/deprecacion manual.

Falta para produccion:

- Auditoria de inferencias productivas.
- Comparacion entre versiones.

Tabla minima `model_assets`:

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

Estados:

- `candidate`
- `active`
- `deprecated`
- `failed`

## Ciclo de vida ML requerido

Este debe ser el flujo real del sistema:

```text
1. Sincronizar datos legacy / ingresar datos nuevos
2. Diagnosticar cobertura y calidad
3. Ejecutar limpieza auditable
4. Crear feature set
5. Lanzar training job
6. Evaluar metricas
7. Registrar artefacto
8. Activar version
9. Ejecutar inferencia real
10. Registrar trazabilidad
11. Monitorear drift/desempeno
12. Reentrenar cuando aplique
```

Si el sistema no puede hacer esos 12 pasos desde API, todavia no es un backend ML completo.

## Arquitectura funcional local propuesta

```text
backend/app
  api/v1
    datasets.py
    data_quality.py
    features.py
    ml_lifecycle.py
    models.py
  application
    dataset_service.py
    cleaning_service.py
    feature_service.py
    training_service.py
    model_asset_service.py
  models_engine
    ml
      preprocessing.py
      tabular_algorithms.py
      sequence_algorithms.py
      training_pipeline.py
      artifact_registry.py
  infrastructure
    db/models
      ml_lifecycle.py
    repositories
      dataset_repository.py
      cleaning_repository.py
      feature_repository.py
      training_repository.py
      model_asset_repository.py
```

No deben crearse notebooks ni scripts sueltos. Todo debe vivir como servicio backend, con rutas API y persistencia.

## Contrato minimo para frontend

### Pantalla 1: Datos

Usa:

- `GET /datasets/sources`
- `POST /datasets/sync-legacy`
- `GET /datasets/coverage?pond_id={pond_id}`
- `GET /datasets/readiness?pond_id={pond_id}&model_code={model_code}`

Debe mostrar:

- estanques;
- variables disponibles;
- registros por variable;
- fecha inicial y final;
- completitud;
- variables faltantes por modelo.

### Pantalla 2: Limpieza

Usa:

- `POST /data/cleaning-runs`
- `GET /data/cleaning-runs/{run_id}`
- `GET /data/cleaning-runs/{run_id}/summary`
- `GET /data/cleaning-runs/{run_id}/preview`

Debe mostrar:

- puntos crudos;
- puntos limpios;
- outliers 3-sigma;
- vacios interpolados;
- metodo usado;
- boton para aprobar dataset limpio.

### Pantalla 3: Features

Usa:

- `POST /features/build`
- `GET /features/{feature_set_id}`
- `GET /features/{feature_set_id}/preview`
- `GET /features/{feature_set_id}/columns`

Debe mostrar:

- variable objetivo;
- columnas predictoras;
- Pearson score;
- ventana temporal;
- split train/validation/test.

### Pantalla 4: Entrenamiento

Usa:

- `GET /ml/trainable-models`
- `POST /ml/training-jobs`
- `GET /ml/training-jobs/{job_id}`
- `GET /ml/training-jobs/{job_id}/events`

Debe mostrar:

- modelos entrenables;
- dataset usado;
- hiperparametros;
- estado del job;
- logs resumidos;
- metricas.

### Pantalla 5: Artefactos

Usa:

- `GET /ml/model-assets`
- `GET /ml/model-assets/{asset_id}`
- `POST /ml/model-assets/{asset_id}/activate`
- `POST /ml/model-assets/{asset_id}/deprecate`

Debe mostrar:

- versiones por modelo;
- metricas;
- fecha de entrenamiento;
- estado activo/candidato/deprecado;
- boton "activar version".

### Pantalla 6: Inferencia

Usa:

- `GET /models/{model_code}/input-audit`
- `POST /models/{model_code}/run`
- `GET /models/{model_code}/metrics`
- `GET /models/{model_code}/asset`

Debe mostrar:

- si el modelo usa formula o artefacto;
- inputs automaticos desde BD;
- inputs faltantes;
- version activa;
- salida;
- trazabilidad.

## Modelos por tipo de ciclo de vida

### Deterministas

No se entrenan. Se calibran o parametrizan.

Incluyen:

- oxigeno 0D;
- oxigeno 1D;
- RAS;
- crecimiento Soderberg/Yi;
- bioenergetica;
- racion;
- zootecnia;
- reglas de saciedad.

Ciclo:

```text
input-audit -> test-payload -> run -> model_outputs
```

Debe agregarse:

- calibracion opcional;
- registro formal en `model_run`;
- parametros versionados.

### ML tabular

Se entrenan con historico tabular.

Incluyen:

- regresion lineal/logistica;
- SVM/SVR;
- Random Forest;
- Decision Tree;
- KNN;
- K-Means;
- PCA;
- SOM;
- Q-Learning simulado.

Ciclo:

```text
dataset -> cleaning -> feature_set -> training_job -> model_asset -> activate -> run
```

### ML secuencial

Se entrenan con series temporales.

Incluyen:

- LSTM;
- Pearson-LSTM;
- Pearson-LSTM-Attention;
- BPNN-MEA.

Ciclo:

```text
dataset -> cleaning -> windows/look-back -> training_job -> model_asset -> activate -> forecast
```

### Vision/CFD/externos

No pueden completarse con la telemetria tabular actual.

Incluyen:

- segmentacion de mallas;
- saciedad por video;
- tracking de comportamiento;
- CFD de alimento;
- vision para conteo/tamano si no hay dataset visual.

Ciclo:

```text
external_dataset_required -> metadata/dry-run -> train only when dataset exists
```

## Fases de implementacion correctas

### Fase A: Diagnostico de datos

Implementar:

- tablas `dataset_snapshots`, `dataset_variable_coverage`;
- rutas `/datasets/*`;
- resumen por modelo de inputs disponibles/faltantes.

Resultado:

- El frontend sabe si un modelo se puede entrenar antes de mostrar botones inutiles.

### Fase B: Limpieza real

Implementar:

- `cleaning_runs`;
- pipeline interpolacion + 3-sigma + MinMax;
- preview antes/despues;
- escritura de `clean_measurements` con flags reales.

Resultado:

- El sistema limpia datos historicos desde backend.

### Fase C: Feature sets

Implementar:

- constructor de datasets tabulares;
- constructor de ventanas temporales;
- Pearson selector;
- split 70/15/15.

Resultado:

- Entrenamientos usan feature sets versionados, no consultas sueltas.

### Fase D: Training jobs

Implementar:

- `training_jobs`;
- `training_job_events`;
- jobs sincronos cortos inicialmente;
- preparacion para worker asincrono.

Resultado:

- El frontend puede lanzar entrenamiento y consultar progreso.

### Fase E: Model assets

Implementar:

- `model_assets`;
- guardado de artefactos;
- metricas;
- activacion/deprecacion;
- consulta por `model_code`.

Resultado:

- Un modelo entrenado queda versionado y reutilizable.

### Fase F: Inference con artefacto activo

Implementar:

- carga de artefacto activo en runners ML;
- `input-audit` desbloqueado por artefacto;
- `run` productivo;
- trazabilidad.

Resultado:

- El backend deja de ser demo para modelos ML y hace inferencia real.

### Fase G: Monitoreo y reentrenamiento

Implementar:

- conteo de inferencias;
- ultimas metricas;
- drift basico;
- recomendacion de reentrenamiento;
- comparacion de versiones.

Resultado:

- Ciclo de vida continuo.

## Definicion de terminado

La imagen estara funcional cuando desde frontend se pueda hacer:

1. elegir granja y estanque;
2. ver cobertura real de datos;
3. ejecutar limpieza;
4. aprobar dataset limpio;
5. construir feature set;
6. entrenar modelo ML;
7. ver metricas;
8. activar artefacto;
9. ejecutar inferencia real;
10. ver trazabilidad y version usada.

Y desde backend existan:

- rutas `/datasets`;
- rutas `/data/cleaning-runs`;
- rutas `/features`;
- rutas `/ml/training-jobs`;
- rutas `/ml/model-assets`;
- runners ML conectados a artefactos activos;
- tests de ciclo completo.

## Estado final esperado por componente visual

```text
Fuentes de datos                 -> dataset coverage operativo
Persistencia relacional MySQL    -> tablas MLOps en aquaculture_digital_twin
Bus de calidad                   -> cleaning_runs ejecutables
Ingenieria de datos              -> feature_sets versionados
Motor determinista               -> ya funcional, falta trazabilidad formal completa
Pipeline ML                      -> pendiente de implementar
API dinamica                     -> parcial, falta ciclo ML
Interfaz web                     -> debe consumir estados ML, no inventarlos
Gobernanza MLOps                 -> pendiente de implementar
Despliegue                       -> Docker/VPS listo, falta publicar nuevas rutas al desplegar
```

## Prioridad inmediata

La siguiente implementacion debe ser:

1. `datasets` y cobertura;
2. `cleaning_runs`;
3. `feature_sets`;
4. `training_jobs`;
5. `model_assets`;
6. desbloqueo de modelos ML con artefacto activo.

No conviene agregar mas modelos hasta cerrar ese nucleo. Lo urgente es que el backend deje de ser solo ejecutor de formulas y pase a ser plataforma MLOps acuicola completa.
