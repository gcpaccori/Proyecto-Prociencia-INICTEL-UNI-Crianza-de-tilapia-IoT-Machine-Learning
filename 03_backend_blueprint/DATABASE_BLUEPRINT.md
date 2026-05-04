# DATABASE_BLUEPRINT.md

## Motor recomendado

```text
PostgreSQL + TimescaleDB
```

PostgreSQL manejará entidades de negocio. TimescaleDB manejará series temporales.

## Esquemas

```text
core
geo
aquaculture
iot
timeseries
models
ml
vision
decision
actuation
audit
```

## Tablas base

```text
core.organization
core.user
core.role
core.permission
core.project
core.file_asset
```

```text
aquaculture.farm
aquaculture.pond
aquaculture.channel
aquaculture.raceway
aquaculture.species
aquaculture.culture_cycle
aquaculture.fish_batch
aquaculture.fish_population_event
aquaculture.mortality_event
aquaculture.biomass_sampling
```

## Sensores e IoT

```text
iot.sensor
iot.sensor_type
iot.sensor_calibration
iot.sensor_measurement_raw
iot.sensor_measurement_clean
iot.sensor_status_event
iot.ingestion_batch
```

Campos mínimos para medición cruda:

```text
id
time
farm_id
pond_id
sensor_id
variable_code
raw_value
raw_unit
raw_payload
source_type
created_at
```

Campos mínimos para medición limpia:

```text
id
raw_measurement_id
time
farm_id
pond_id
sensor_id
variable_code
clean_value
standard_unit
quality_flag
validation_status
cleaning_method
created_at
```

## Series temporales

Hypertables sugeridas:

```text
timeseries.sensor_measurements
timeseries.water_quality_timeseries
timeseries.fish_biomass_timeseries
timeseries.feeding_timeseries
timeseries.model_predictions_timeseries
timeseries.derived_features_timeseries
```

Variables principales:

```text
water_temperature
dissolved_oxygen
ph
ammonia_total
unionized_ammonia
nitrite
nitrate
orp
turbidity
co2
salinity
water_flow
water_level
fish_biomass
fish_average_weight
feed_amount
mortality_count
```

## Alimentación

```text
aquaculture.feed_product
aquaculture.feed_composition
aquaculture.feeding_plan
aquaculture.feeding_event
aquaculture.feeding_phase
aquaculture.feed_recommendation
aquaculture.feed_waste_estimation
```

Campos de composición:

```text
protein_pct
lipid_pct
carbohydrate_pct
energy_kj_g
digestibility_protein
digestibility_lipid
digestibility_carb
```

## Modelos

```text
models.model_definition
models.model_version
models.model_source_reference
models.model_parameter
models.model_parameter_set
models.model_input_schema
models.model_output_schema
models.model_run
models.model_run_input
models.model_run_output
models.model_validation_metric
models.model_limitation
```

`model_run` debe ser obligatorio para toda predicción o simulación.

## Predicciones y simulación

```text
timeseries.model_prediction
timeseries.forecast_horizon
timeseries.simulation_result
timeseries.digital_twin_state
timeseries.risk_index
```

Campos mínimos de predicción:

```text
time
target_time
model_version_id
run_id
input_window_start
input_window_end
predicted_variable
predicted_value
unit
confidence
created_at
```

## Visión artificial

```text
vision.camera
vision.media_asset
vision.vision_model_run
vision.detected_fish
vision.detected_object
vision.fish_metric
vision.behavior_event
vision.health_event
vision.net_damage_event
vision.algae_event
```

## Decisión y actuación

```text
decision.alert_rule
decision.alert_event
decision.recommendation
decision.recommendation_reason
decision.risk_assessment
decision.action_policy
```

```text
actuation.actuator
actuation.command
actuation.command_result
actuation.manual_approval
```

## Auditoría

```text
audit.audit_log
audit.data_lineage
audit.model_lineage
audit.user_action_log
```

## Regla de oro

Ninguna predicción, recomendación o comando físico puede existir sin:

```text
model_run_id o recommendation_id
timestamp
source_data_window
model_version
input snapshot
output snapshot
warnings
```
