from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app


def _seed_training_dataset(client: TestClient) -> str:
    farm_id = client.post(
        "/api/v1/farms",
        json={"code": "FARM-ML", "name": "ML Farm"},
    ).json()["id"]
    pond_id = client.post(
        "/api/v1/ponds",
        json={"farm_id": farm_id, "code": "POND-ML", "name": "ML Pond"},
    ).json()["id"]
    sensor_ids: dict[str, str] = {}
    for variable_code in (
        "water_temperature_c",
        "ph",
        "nitrate_ion",
        "dissolved_oxygen_mg_l",
    ):
        sensor_ids[variable_code] = client.post(
            "/api/v1/sensors",
            json={
                "farm_id": farm_id,
                "pond_id": pond_id,
                "sensor_code": f"SENSOR-{variable_code}",
                "variable_code": variable_code,
            },
        ).json()["id"]

    units = {
        "water_temperature_c": "degC",
        "ph": "pH",
        "nitrate_ion": "source_unit",
        "dissolved_oxygen_mg_l": "mg/L",
    }
    for index in range(12):
        timestamp = f"2026-05-01T00:{index:02d}:00Z"
        values = {
            "water_temperature_c": 26.0 + index * 0.1,
            "ph": 7.4 + index * 0.01,
            "nitrate_ion": 0.10 + index * 0.005,
            "dissolved_oxygen_mg_l": 6.8 - index * 0.05,
        }
        for variable_code, value in values.items():
            client.post(
                "/api/v1/measurements/ingest",
                json={
                    "time": timestamp,
                    "farm_id": farm_id,
                    "pond_id": pond_id,
                    "sensor_id": sensor_ids[variable_code],
                    "variable_code": variable_code,
                    "raw_value": value,
                    "raw_unit": units[variable_code],
                },
            )
    return pond_id


def test_ml_lifecycle_executes_dataset_clean_feature_train_asset_flow() -> None:
    app = create_app(Settings(environment="test", enable_docs=True))
    client = TestClient(app)
    pond_id = _seed_training_dataset(client)

    sources = client.get("/api/v1/datasets/sources")
    assert sources.status_code == 200
    assert sources.json()[0]["access_mode"] == "read_only"

    coverage = client.get("/api/v1/datasets/coverage", params={"pond_id": pond_id})
    assert coverage.status_code == 200
    coverage_payload = coverage.json()
    assert coverage_payload["total_records"] >= 48
    assert "dissolved_oxygen_mg_l" in coverage_payload["trainable_variables"]

    readiness = client.get(
        "/api/v1/datasets/readiness",
        params={"pond_id": pond_id, "model_code": "ML_SUPERVISED_LINEAR_REG"},
    )
    assert readiness.status_code == 200
    assert readiness.json()["can_train"] is True

    cleaning = client.post(
        "/api/v1/data/cleaning-runs",
        json={
            "pond_id": pond_id,
            "apply_interpolation": True,
            "apply_sigma3": True,
            "apply_minmax": False,
        },
    )
    assert cleaning.status_code == 201
    cleaning_payload = cleaning.json()
    assert cleaning_payload["status"] == "completed"
    assert cleaning_payload["records_out"] >= 48
    run_id = cleaning_payload["run_id"]

    preview = client.get(f"/api/v1/data/cleaning-runs/{run_id}/preview")
    assert preview.status_code == 200
    assert preview.json()["records"] >= 48

    feature_set = client.post(
        "/api/v1/features/build",
        json={
            "pond_id": pond_id,
            "cleaning_run_id": run_id,
            "target_variable": "dissolved_oxygen_mg_l",
            "feature_variables": ["water_temperature_c", "ph", "nitrate_ion"],
            "window_size": 1,
            "horizon": 1,
        },
    )
    assert feature_set.status_code == 201
    feature_payload = feature_set.json()
    assert feature_payload["rows_count"] >= 12
    assert feature_payload["train_rows"] > 0
    feature_set_id = feature_payload["feature_set_id"]

    train = client.post(
        "/api/v1/ml/training-jobs",
        json={
            "model_code": "ML_SUPERVISED_LINEAR_REG",
            "feature_set_id": feature_set_id,
            "hyperparameters": {"learning_rate": 0.0001, "epochs": 80},
            "auto_activate": True,
        },
    )
    assert train.status_code == 201
    train_payload = train.json()
    assert train_payload["status"] == "completed"
    assert train_payload["asset_id"] is not None
    assert "rmse" in train_payload["metrics"]

    events = client.get(f"/api/v1/ml/training-jobs/{train_payload['job_id']}/events")
    assert events.status_code == 200
    assert [event["event_type"] for event in events.json()] == [
        "queued",
        "running",
        "completed",
    ]

    active_asset = client.get("/api/v1/models/ML_SUPERVISED_LINEAR_REG/asset")
    assert active_asset.status_code == 200
    assert active_asset.json()["status"] == "active"

    metrics = client.get("/api/v1/models/ML_SUPERVISED_LINEAR_REG/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["active_asset_id"] == train_payload["asset_id"]

    prediction = client.post(
        "/api/v1/models/ML_SUPERVISED_LINEAR_REG/predict",
        json={
            "features": {
                "water_temperature_c": 27.0,
                "ph": 7.5,
                "nitrate_ion": 0.15,
            }
        },
    )
    assert prediction.status_code == 200
    assert prediction.json()["asset_id"] == train_payload["asset_id"]
    assert prediction.json()["traceability"]["feature_set_id"] == feature_set_id

    lifecycle = client.get("/api/v1/ml/lifecycle/status")
    assert lifecycle.status_code == 200
    assert lifecycle.json()["training_enabled"] is True
    assert lifecycle.json()["active_model_assets"] == 1

    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/datasets/coverage" in paths
    assert "/api/v1/data/cleaning-runs" in paths
    assert "/api/v1/features/build" in paths
    assert "/api/v1/ml/training-jobs" in paths
    assert "/api/v1/ml/model-assets/{asset_id}/activate" in paths
    assert "/api/v1/models/{model_code}/predict" in paths
