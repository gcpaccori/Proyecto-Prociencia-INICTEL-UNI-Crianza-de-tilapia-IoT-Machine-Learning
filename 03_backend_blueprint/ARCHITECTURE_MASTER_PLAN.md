# ARCHITECTURE_MASTER_PLAN.md

## Arquitectura backend recomendada

Usar un monolito modular profesional en Python, preparado para separarse luego en microservicios si la operación crece.

```text
backend/
  app/
    api/
    core/
    domains/
    infrastructure/
    models_engine/
    workers/
    shared/
    tests/
  migrations/
  scripts/
  notebooks_validacion/
  docs_modelos/
```

## Stack base

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
OpenCV
PyTorch/TensorFlow/scikit-learn
NumPy/Pandas/SciPy
```

## Flujo global

```text
1. Captura de datos
   Sensores IoT, cámaras, alimentación, biomasa, mortalidad y operación manual.

2. Ingesta backend
   HTTP, MQTT, CSV, Excel, carga manual o integración externa.

3. Validación
   Unidades, rangos físicos, sensor válido, estanque válido, timestamp y duplicados.

4. Normalización
   °C, mg/L, kg, g, L/h, m3/h, %, h, día.

5. Almacenamiento bruto
   Guardar dato original sin modificar.

6. Limpieza
   Outliers, faltantes, interpolación, estado del sensor y bandera de calidad.

7. Almacenamiento curado
   Guardar dato limpio para modelos.

8. Feature engineering
   Ventanas temporales, medias móviles, tendencia, fase productiva, biomasa estimada.

9. Ejecución de modelos
   OD, amonio, bioenergético, alimentación, LSTM, BPNN, visión artificial.

10. Resultados
   Predicciones, simulaciones, alertas, recomendaciones.

11. Decisión
   Motor prescriptivo decide si recomendar acción.

12. Actuación
   Manual o automática: aireador, comedero, bomba, válvula.

13. Auditoría
   Guardar entrada, salida, modelo, versión, decisión y usuario/sistema.
```

## Estructura de código

```text
app/
  main.py

  core/
    config.py
    security.py
    database.py
    logging.py
    exceptions.py

  shared/
    units/
    time/
    schemas/
    enums/
    validators/

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
      sparus_aurata_growth.py
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

  infrastructure/
    db/
    repositories/
    object_storage/
    mqtt/
    queues/
    mlflow/
    external_devices/

  workers/
    ingest_worker.py
    model_worker.py
    vision_worker.py
    alert_worker.py

  api/
    v1/
      farms.py
      ponds.py
      sensors.py
      measurements.py
      models.py
      predictions.py
      digital_twin.py
      vision.py
      alerts.py
      actuation.py
```

## Orden de implementación

1. Base: FastAPI, PostgreSQL, TimescaleDB, Alembic, estructura modular.
2. Dominios: granja, estanque, sensor, especie, lote, ciclo productivo.
3. Ingesta IoT: raw/clean measurements.
4. Registry de modelos: definición, versión, parámetros, entradas, salidas, runs.
5. Modelos OD y amonio.
6. Modelos bioenergéticos.
7. Modelos de alimentación.
8. Modelos ML: BPNN-MEA y Pearson-LSTM-AM.
9. Visión artificial.
10. Orquestador de Gemelo Digital.
11. Recomendaciones, alertas y actuación.
12. Auditoría, seguridad y reportes.
