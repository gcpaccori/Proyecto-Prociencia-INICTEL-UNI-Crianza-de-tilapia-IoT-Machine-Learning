# API_ENDPOINTS.md

## Endpoints mínimos del backend

### Granja, estanques y ciclos

```text
POST /api/v1/farms
GET  /api/v1/farms
GET  /api/v1/farms/{farm_id}
POST /api/v1/ponds
GET  /api/v1/ponds/{pond_id}
POST /api/v1/culture-cycles
GET  /api/v1/culture-cycles/{cycle_id}
```

### Sensores e ingesta

```text
POST /api/v1/sensors
GET  /api/v1/sensors/{sensor_id}
POST /api/v1/measurements/ingest
POST /api/v1/measurements/batch-ingest
GET  /api/v1/ponds/{pond_id}/measurements
GET  /api/v1/ponds/{pond_id}/timeseries
```

### Estado actual

```text
GET /api/v1/ponds/{pond_id}/state
GET /api/v1/ponds/{pond_id}/water-quality/current
GET /api/v1/ponds/{pond_id}/biomass/current
GET /api/v1/ponds/{pond_id}/feeding/current
```

### Modelos

```text
GET  /api/v1/models
GET  /api/v1/models/{model_code}
POST /api/v1/models/{model_code}/run
GET  /api/v1/models/runs/{run_id}
GET  /api/v1/models/runs/{run_id}/explanation
```

### Predicción y simulación

```text
POST /api/v1/predictions/dissolved-oxygen
POST /api/v1/predictions/ammonia
POST /api/v1/predictions/feed-intake
POST /api/v1/predictions/water-quality
POST /api/v1/simulations/scenario
GET  /api/v1/predictions/{prediction_id}
```

### Gemelo Digital

```text
POST /api/v1/digital-twin/{pond_id}/snapshot
GET  /api/v1/digital-twin/{pond_id}/latest
POST /api/v1/digital-twin/{pond_id}/simulate
GET  /api/v1/digital-twin/{pond_id}/risks
GET  /api/v1/digital-twin/{pond_id}/recommendations
```

### Visión artificial

```text
POST /api/v1/vision/media
POST /api/v1/vision/infer
GET  /api/v1/vision/inferences/{run_id}
GET  /api/v1/ponds/{pond_id}/vision/fish-metrics
GET  /api/v1/ponds/{pond_id}/vision/behavior-events
```

### Alertas y decisiones

```text
GET  /api/v1/alerts
GET  /api/v1/alerts/{alert_id}
POST /api/v1/recommendations/{recommendation_id}/approve
POST /api/v1/recommendations/{recommendation_id}/reject
```

### Actuadores

```text
POST /api/v1/actuators
GET  /api/v1/actuators/{actuator_id}
POST /api/v1/actuators/{actuator_id}/command
GET  /api/v1/actuators/{actuator_id}/commands
```

## Contrato estándar para ejecutar un modelo

Request:

```json
{
  "pond_id": "POND-001",
  "culture_cycle_id": "CYCLE-001",
  "input_window": {
    "start": "2026-04-01T00:00:00Z",
    "end": "2026-04-01T12:00:00Z"
  },
  "parameters": {},
  "options": {
    "save_run": true,
    "dry_run": false
  }
}
```

Response:

```json
{
  "run_id": "RUN-001",
  "model_code": "DO_DYNAMIC_0D_ROYER_2021",
  "model_version": "1.0.0",
  "source_report": "INFORME016",
  "status": "completed",
  "outputs": {},
  "unit_map": {},
  "confidence": null,
  "warnings": [],
  "explanation": "..."
}
```
