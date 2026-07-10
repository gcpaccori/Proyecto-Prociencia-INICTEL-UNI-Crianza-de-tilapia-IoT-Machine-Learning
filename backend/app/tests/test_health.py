from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app


def test_health_endpoint_returns_service_status() -> None:
    app = create_app(Settings(environment="test"))
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "Aquaculture Digital Twin Backend"
    assert payload["version"] == "0.1.0"
    assert payload["environment"] == "test"
    assert "timestamp" in payload


def test_openapi_schema_is_available_when_docs_are_enabled() -> None:
    app = create_app(Settings(environment="test", enable_docs=True))
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Aquaculture Digital Twin Backend"


def test_real_model_routes_are_exposed_by_the_vm_app() -> None:
    app = create_app(Settings(environment="test", enable_docs=True))
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/ponds/{pond_id}/models/svm-od/train" in paths
    assert "/api/v1/ponds/{pond_id}/models/svm-od/forecast" in paths
    assert "/api/v1/ponds/{pond_id}/models/oxygen/status" in paths
    assert "/api/v1/ponds/{pond_id}/models/tilapia-growth" in paths
    assert "/api/v1/ponds/{pond_id}/ai/dashboard" in paths
