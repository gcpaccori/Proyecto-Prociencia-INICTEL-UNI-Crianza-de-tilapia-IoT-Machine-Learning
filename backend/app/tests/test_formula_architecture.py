import math

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.models_engine.deterministic import (
    do_saturation,
    haskell_feed_rate,
    ras_oxygen_balance,
    soderberg_delta_l,
    update_do_0d,
    update_do_1d,
    yi_growth_rate,
    zootechnic_indexes,
)
from backend.app.models_engine.ml.preprocessing import (
    linear_interpolate_missing,
    make_time_windows,
    minmax_normalize,
    pearson_correlation,
    sigma3_flags,
    temporal_train_validation_test_split,
)


def test_deterministic_formula_core_has_no_nan_outputs() -> None:
    assert do_saturation(25.0) == pytest.approx(8.5561875)
    assert update_do_0d(6.0, 7.0, 1000.0, 2000.0, 0.2, 0.05, 8.9, 20.0, 10.0, 1.0) >= 0
    assert update_do_1d([6.0, 5.8], [8.9, 8.9], [10.0, 20.0], 1.0, 0.05, 10.0, 4.0, 2.0, 1.0)
    ras = ras_oxygen_balance(6.0, 80.0, 27.0, 3.2, 1200, 30.0, 96.0, 1.0)
    growth = yi_growth_rate(
        temperature_c=27.0,
        dissolved_oxygen_mg_l=6.0,
        fish_weight_g=80.0,
        t_min_c=18.0,
        t_opti_c=28.0,
        t_max_c=34.0,
        do_min_mg_l=3.0,
        do_crit_mg_l=5.0,
        k_min=0.001,
        s=0.05,
        kappa=1.0,
        phi=1.0,
        h=1.0,
        feeding_level=0.8,
        m=0.67,
        n=0.8,
    )
    soderberg = soderberg_delta_l(27.0, "nile tilapia")
    indexes = zootechnic_indexes(120.0, 80.0, 18.0, 30.0, 1000, 1200, 30000.0)

    for payload in (ras, growth, soderberg, indexes):
        for value in payload.values():
            if isinstance(value, float):
                assert not math.isnan(value)
    assert 0 <= growth["tau"] <= 1
    assert 0 <= growth["delta"] <= 1
    assert haskell_feed_rate(1.5, 2.0, 100.0) == pytest.approx(9.0)


def test_ml_preprocessing_contracts() -> None:
    assert minmax_normalize(5, 5, 5) == 0.0
    assert linear_interpolate_missing([1.0, None, 3.0]) == [1.0, 2.0, 3.0]
    assert sigma3_flags([1.0, 1.0, 1.0]) == [False, False, False]
    assert pearson_correlation([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)
    assert make_time_windows([1, 2, 3, 4], 2) == [
        {"x": [1.0, 2.0], "y": 3.0},
        {"x": [2.0, 3.0], "y": 4.0},
    ]
    split = temporal_train_validation_test_split(list(range(10)), 0.6, 0.2)
    assert split["train"] == [0, 1, 2, 3, 4, 5]
    assert split["validation"] == [6, 7]
    assert split["test"] == [8, 9]


def test_classified_model_routes_use_common_runner_contract() -> None:
    client = TestClient(create_app(Settings(environment="test")))

    response = client.post(
        "/api/v1/models/do/simulate-0d",
        json={
            "pond_id": "POND-1",
            "inputs": {
                "do_initial_mg_l": {"value": 6.2, "unit": "mg/L"},
                "do_influent_mg_l": {"value": 7.1, "unit": "mg/L"},
                "water_temperature_c": {"value": 27.0, "unit": "degC"},
                "flow_rate_l_h": {"value": 1200.0, "unit": "L/h"},
                "raceway_volume_l": {"value": 1280.0, "unit": "L"},
                "fish_biomass_kg": {"value": 120.0, "unit": "kg"},
                "fish_respiration_rate_mg_h_kg": {"value": 20.0, "unit": "mg/h/kg"},
                "oxygen_supply_rate_mg_l_h": {"value": 0.2, "unit": "mg/L/h"},
                "reaeration_rate_h_1": {"value": 0.046, "unit": "h^-1"},
                "simulation_horizon_minutes": {"value": 60, "unit": "min"},
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_code"] == "DO_DYNAMIC_0D_ROYER_2021"
    assert payload["outputs"]["do_forecast_mg_l"]["value"] >= 0

    catalog = client.get("/api/v1/models").json()
    codes = {item["model_code"] for item in catalog}
    assert "DO_TRANSPORT_1D" in codes
    assert "RAS_OXYGEN_BALANCE" in codes
    assert "YI_ENVIRONMENTAL_GROWTH" in codes
    assert "SODERBERG_LINEAR_GROWTH" in codes
    assert "ZOOTECHNIC_INDEXES" in codes


def test_all_catalog_models_can_generate_and_execute_test_payloads() -> None:
    client = TestClient(create_app(Settings(environment="test")))

    catalog_response = client.get("/api/v1/models")
    assert catalog_response.status_code == 200
    catalog = catalog_response.json()
    assert catalog

    for model in catalog:
        model_code = model["model_code"]
        payload_response = client.get(
            f"/api/v1/models/{model_code}/test-payload",
            params={"pond_id": "POND-GENERATED-TEST"},
        )
        assert payload_response.status_code == 200, model_code
        payload = payload_response.json()
        generated_request = payload["request"]
        assert payload["model_code"] == model_code
        assert set(model["inputs"]).issubset(generated_request["inputs"])
        assert payload["generated_input_names"] or payload["auto_input_names"]

        run_response = client.post(
            f"/api/v1/models/{model_code}/test-run",
            params={"pond_id": "POND-GENERATED-TEST"},
        )
        assert run_response.status_code == 200, f"{model_code}: {run_response.text}"
        output = run_response.json()
        assert output["model_code"] == model_code
        assert output["run_id"].startswith("RUN-")

        if model["readiness_status"] == "requires_external_artifact":
            assert output["warnings"]
