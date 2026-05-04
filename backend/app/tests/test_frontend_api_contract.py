from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app


def test_frontend_flow_ingests_state_creates_snapshot_and_actuation_command() -> None:
    app = create_app(Settings(environment="test"))
    client = TestClient(app)

    farm_response = client.post(
        "/api/v1/farms",
        json={"code": "FARM-UI", "name": "Frontend Farm"},
    )
    assert farm_response.status_code == 201
    farm_id = farm_response.json()["id"]

    pond_response = client.post(
        "/api/v1/ponds",
        json={"farm_id": farm_id, "code": "POND-UI", "name": "Pond UI"},
    )
    assert pond_response.status_code == 201
    pond_id = pond_response.json()["id"]

    sensor_response = client.post(
        "/api/v1/sensors",
        json={
            "farm_id": farm_id,
            "pond_id": pond_id,
            "sensor_code": "TEMP-001",
            "variable_code": "water_temperature_c",
        },
    )
    assert sensor_response.status_code == 201
    sensor_id = sensor_response.json()["id"]

    ingest_response = client.post(
        "/api/v1/measurements/ingest",
        json={
            "farm_id": farm_id,
            "pond_id": pond_id,
            "sensor_id": sensor_id,
            "variable_code": "water_temperature_c",
            "raw_value": 18.4,
            "raw_unit": "degC",
            "source_type": "manual",
        },
    )
    assert ingest_response.status_code == 201
    assert ingest_response.json()["clean_measurement"]["quality_flag"] == "valid"

    state_response = client.get(f"/api/v1/ponds/{pond_id}/state")
    assert state_response.status_code == 200
    state_payload = state_response.json()
    assert "water_temperature_c" in state_payload["water_quality_current"]

    snapshot_response = client.post(
        f"/api/v1/digital-twin/{pond_id}/snapshot",
        json={},
    )
    assert snapshot_response.status_code == 201
    snapshot_payload = snapshot_response.json()
    assert snapshot_payload["pond_id"] == pond_id
    assert snapshot_payload["risk_assessments"]
    assert snapshot_payload["recommendations"]
    assert snapshot_payload["alerts"]

    alerts_response = client.get("/api/v1/alerts", params={"pond_id": pond_id})
    assert alerts_response.status_code == 200
    assert alerts_response.json()[0]["snapshot_id"] == snapshot_payload["snapshot_id"]

    recommendations_response = client.get(
        "/api/v1/recommendations",
        params={"pond_id": pond_id},
    )
    assert recommendations_response.status_code == 200
    recommendation_code = recommendations_response.json()[0]["recommendation_code"]

    actuator_response = client.post(
        "/api/v1/actuators",
        json={
            "farm_id": farm_id,
            "pond_id": pond_id,
            "actuator_code": "AERATOR-001",
            "actuator_type": "aerator",
            "status": "active",
        },
    )
    assert actuator_response.status_code == 201

    command_response = client.post(
        "/api/v1/actuation-commands/from-recommendation",
        json={
            "recommendation_code": recommendation_code,
            "safety_policy": {
                "allow_automatic_commands": True,
                "allowed_actuator_types": ["aerator"],
                "manual_approval_required": True,
            },
            "user_approval": {
                "approved": True,
                "approved_by": "operator-ui",
            },
        },
    )
    assert command_response.status_code == 200
    command_payload = command_response.json()
    assert command_payload["command_status"] == "pending_dispatch"
    assert command_payload["command"]["command_id"].startswith("COMMAND-")
    assert command_payload["command"]["execution_status"] == "pending_dispatch"


def test_model_catalog_and_direct_model_run_are_exposed_for_frontend() -> None:
    app = create_app(Settings(environment="test"))
    client = TestClient(app)

    catalog_response = client.get("/api/v1/models")
    assert catalog_response.status_code == 200
    model_codes = {item["model_code"] for item in catalog_response.json()}
    assert "FEEDING_SATIETY_RULES" in model_codes
    assert "DO_DYNAMIC_0D_ROYER_2021" in model_codes

    run_response = client.post(
        "/api/v1/models/FEEDING_SATIETY_RULES/run",
        json={
            "pond_id": "POND-API",
            "inputs": {
                "feeding_behavior_category": {
                    "value": "NO_REACTION",
                    "unit": "category",
                },
                "feed_remaining": {"value": True, "unit": "boolean"},
                "fish_reaction": {"value": "no reaction", "unit": "text"},
            },
        },
    )
    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["run_id"].startswith("RUN-")
    assert payload["outputs"]["stop_feeding"]["value"] is True
    assert payload["outputs"]["feed_waste_risk"]["value"] == "high"


def test_openapi_exposes_frontend_backend_contract_paths() -> None:
    app = create_app(Settings(environment="test", enable_docs=True))
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/farms" in paths
    assert "/api/v1/measurements/ingest" in paths
    assert "/api/v1/digital-twin/{pond_id}/snapshot" in paths
    assert "/api/v1/alerts" in paths
    assert "/api/v1/actuation-commands/from-recommendation" in paths
