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

    projection_response = client.post(
        f"/api/v1/digital-twin/{pond_id}/projection",
        json={
            "horizon_hours": 12,
            "step_hours": 3,
            "selected_models": ["DO_DYNAMIC_0D_ROYER_2021"],
            "variable_adjustments_per_hour": {"water_temperature_c": 0.1},
            "operational_controls": {
                "aeration_percent": 70,
                "filtration_percent": 55,
                "fish_count": 100,
                "average_weight_g": 120,
                "tank_volume_m3": 10,
                "feed_conversion_ratio": 1.5,
            },
        },
    )
    assert projection_response.status_code == 200
    projection = projection_response.json()
    assert projection["pond_id"] == pond_id
    assert [point["hour"] for point in projection["points"]] == [0, 3, 6, 9, 12]
    assert projection["baseline_values"]["water_temperature_c"] == 18.4
    assert projection["baseline_observed_at"]["water_temperature_c"]
    assert projection["baseline_ingested_at"]["water_temperature_c"]
    assert projection["baseline_units"]["water_temperature_c"] == "degC"
    assert projection["baseline_quality_flags"]["water_temperature_c"] == "valid"
    assert projection["scenario_adjustments_per_hour"]["water_temperature_c"] == 0.1
    assert projection["operational_controls"]["aeration_percent"] == 70
    assert projection["traceability"]["operational_controls"]["filtration_percent"] == 55
    assert projection["traceability"]["generated_data_used"] is False
    assert projection["traceability"]["model_layer_semantics"] == "operational_activity_index_not_model_output"
    assert projection["traceability"]["operational_controls_semantics"] == "productive_simulation_inputs_with_explicit_assumptions"
    assert projection["model_participation"][0]["model_code"] == "DO_DYNAMIC_0D_ROYER_2021"
    assert projection["model_participation"][0]["influence_weight"] == 1.0
    assert set(projection["points"][0]["model_activity"]) == {"DO_DYNAMIC_0D_ROYER_2021"}
    assert projection["points"][0]["model_activity"]["DO_DYNAMIC_0D_ROYER_2021"] == 85.0
    assert projection["initial_productive_state"]["fish_count"] == 100
    assert projection["initial_productive_state"]["average_weight_g"] == 120
    assert projection["initial_productive_state"]["biomass_kg"] > 0
    assert projection["simulation_summary"]["final_biomass_kg"] > 0
    assert projection["simulation_summary"]["feed_required_kg"] >= 0
    assert projection["points"][-1]["biological_state"]["average_weight_g"] > 0
    assert 0 <= projection["points"][-1]["operational_state"]["stress_index"] <= 100
    assert projection["simulation_assumptions"]["mortality"].startswith("risk exposure")

    low_aeration_projection = client.post(
        f"/api/v1/digital-twin/{pond_id}/projection",
        json={
            "horizon_hours": 12,
            "step_hours": 3,
            "operational_controls": {
                "aeration_percent": 0,
                "filtration_percent": 0,
                "fish_count": 100,
                "average_weight_g": 120,
                "tank_volume_m3": 10,
            },
        },
    ).json()
    assert (
        projection["points"][-1]["operational_state"]["projected_oxygen_mg_l"]
        > low_aeration_projection["points"][-1]["operational_state"]["projected_oxygen_mg_l"]
    )
    assert (
        projection["points"][-1]["operational_state"]["organic_load_index"]
        < low_aeration_projection["points"][-1]["operational_state"]["organic_load_index"]
    )

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


def test_unprefixed_frontend_aliases_cors_timeseries_and_model_audit() -> None:
    app = create_app(Settings(environment="test"))
    client = TestClient(app)

    cors_response = client.options(
        "/health",
        headers={
            "Origin": "https://example.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert cors_response.status_code == 200
    assert cors_response.headers["access-control-allow-origin"] == "*"

    assert client.get("/health").status_code == 200

    farm_id = client.post(
        "/farms",
        json={"code": "FARM-ALIAS", "name": "Frontend Alias Farm"},
    ).json()["id"]
    pond_id = client.post(
        "/ponds",
        json={"farm_id": farm_id, "code": "POND-ALIAS", "name": "Alias Pond"},
    ).json()["id"]
    temp_sensor_id = client.post(
        "/sensors",
        json={
            "farm_id": farm_id,
            "pond_id": pond_id,
            "sensor_code": "TEMP-ALIAS",
            "variable_code": "water_temperature_c",
        },
    ).json()["id"]
    ph_sensor_id = client.post(
        "/sensors",
        json={
            "farm_id": farm_id,
            "pond_id": pond_id,
            "sensor_code": "PH-ALIAS",
            "variable_code": "ph",
        },
    ).json()["id"]
    do_sensor_id = client.post(
        "/sensors",
        json={
            "farm_id": farm_id,
            "pond_id": pond_id,
            "sensor_code": "DO-ALIAS",
            "variable_code": "dissolved_oxygen_mg_l",
        },
    ).json()["id"]

    for index, value in enumerate((24.1, 24.4), start=1):
        client.post(
            "/measurements/ingest",
            json={
                "time": f"2026-05-05T09:0{index}:00Z",
                "farm_id": farm_id,
                "pond_id": pond_id,
                "sensor_id": temp_sensor_id,
                "variable_code": "water_temperature_c",
                "raw_value": value,
                "raw_unit": "degC",
            },
        )
    client.post(
        "/measurements/ingest",
        json={
            "time": "2026-05-05T09:03:00Z",
            "farm_id": farm_id,
            "pond_id": pond_id,
            "sensor_id": ph_sensor_id,
            "variable_code": "ph",
            "raw_value": 7.8,
            "raw_unit": "pH",
        },
    )
    client.post(
        "/measurements/ingest",
        json={
            "time": "2026-05-05T09:04:00Z",
            "farm_id": farm_id,
            "pond_id": pond_id,
            "sensor_id": do_sensor_id,
            "variable_code": "dissolved_oxygen_mg_l",
            "raw_value": 5.9,
            "raw_unit": "mg/L",
        },
    )

    timeseries_response = client.get(f"/ponds/{pond_id}/timeseries")
    assert timeseries_response.status_code == 200
    timeseries_payload = timeseries_response.json()
    assert [row["variable_code"] for row in timeseries_payload] == [
        "water_temperature_c",
        "water_temperature_c",
    ]
    assert [row["clean_value"] for row in timeseries_payload] == [24.1, 24.4]

    audit_response = client.get(
        "/models/BPNN_MEA_FEED_INTAKE/input-audit",
        params={"pond_id": pond_id},
    )
    assert audit_response.status_code == 200
    audit_payload = audit_response.json()
    assert audit_payload["auto_inputs"]["water_temperature_c"]["value"] == 24.4
    assert audit_payload["auto_inputs"]["dissolved_oxygen_mg_l"]["value"] == 5.9
    assert "average_fish_weight_g" in audit_payload["missing_inputs"]
    assert audit_payload["blocked_by"] == ["trained_artifact_pending"]


def test_openapi_exposes_frontend_backend_contract_paths() -> None:
    app = create_app(Settings(environment="test", enable_docs=True))
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/farms" in paths
    assert "/api/v1/measurements/ingest" in paths
    assert "/api/v1/digital-twin/{pond_id}/snapshot" in paths
    assert "/api/v1/digital-twin/{pond_id}/projection" in paths
    assert "/api/v1/alerts" in paths
    assert "/api/v1/actuation-commands/from-recommendation" in paths
    assert "/api/v1/frontend/dashboard" in paths
    assert "/api/v1/frontend/components" in paths
    assert "/api/v1/models/test-run-all" in paths
    assert "/api/v1/datasets/coverage" in paths
    assert "/api/v1/data/cleaning-runs" in paths
    assert "/api/v1/features/build" in paths
    assert "/api/v1/ml/training-jobs" in paths
    assert "/api/v1/ml/model-assets" in paths


def test_frontend_dashboard_and_batch_model_test_are_ready_for_ui() -> None:
    app = create_app(Settings(environment="test"))
    client = TestClient(app)

    farm_id = client.post(
        "/api/v1/farms",
        json={"code": "FARM-DASH", "name": "Dashboard Farm"},
    ).json()["id"]
    pond_id = client.post(
        "/api/v1/ponds",
        json={
            "farm_id": farm_id,
            "code": "POND-DASH",
            "name": "Dashboard Pond",
            "water_volume_l": 1280,
        },
    ).json()["id"]
    sensor_id = client.post(
        "/api/v1/sensors",
        json={
            "farm_id": farm_id,
            "pond_id": pond_id,
            "sensor_code": "DO-DASH",
            "variable_code": "dissolved_oxygen_mg_l",
        },
    ).json()["id"]
    client.post(
        "/api/v1/measurements/ingest",
        json={
            "farm_id": farm_id,
            "pond_id": pond_id,
            "sensor_id": sensor_id,
            "variable_code": "dissolved_oxygen_mg_l",
            "raw_value": 6.4,
            "raw_unit": "mg/L",
        },
    )

    batch_response = client.post(
        "/api/v1/models/test-run-all",
        params={"pond_id": pond_id},
    )
    assert batch_response.status_code == 200
    batch_payload = batch_response.json()
    assert batch_payload["failed"] == 0
    assert batch_payload["succeeded"] == batch_payload["total"]

    dashboard_response = client.get(
        "/api/v1/frontend/dashboard",
        params={"farm_id": farm_id, "pond_id": pond_id},
    )
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert dashboard["backend"]["status"] == "online"
    assert dashboard["selection"]["pond_id"] == pond_id
    assert dashboard["component_summary"]["total_components"] == 45
    assert dashboard["component_summary"]["integrable_components"] == 40
    assert dashboard["component_summary"]["implemented_components"] == 40
    assert dashboard["component_summary"]["conditioned_components"] == 5
    assert dashboard["component_summary"]["executable_model_runners"] == batch_payload["total"]
    assert dashboard["model_summary"]["test_payload_enabled"] == batch_payload["total"]
    assert dashboard["ml_lifecycle"]["training_enabled"] is True
    assert dashboard["evidence"]["scenarios"] >= batch_payload["total"]
    assert dashboard["traceability"]
    assert dashboard["frontend_contract_routes"]["test_run_all"] == "/models/test-run-all"

    components_response = client.get("/api/v1/frontend/components")
    assert components_response.status_code == 200
    components = components_response.json()
    assert components["total_components"] == 45
    assert components["integrable_components"] == 40
    assert components["implemented_components"] == 40
    assert components["conditioned_components"] == 5
    assert sum(
        1
        for component in components["components"]
        if component["implementation_status"] == "implemented_backend"
    ) == 40
