from __future__ import annotations

from backend.app.application.model_alerts import ModelAlertDashboardService
from backend.app.application.real_models import (
    GROWTH_MODEL_CODE,
    SVM_MODEL_CODE,
    WATER_QUALITY_ICA_MODEL_CODE,
)
from threading import Event
from datetime import datetime, timezone
from types import SimpleNamespace


def _dashboard(*, active_svm: bool = False, forecast: float = 4.2) -> dict[str, object]:
    return {
        "ai_model": {"productive": active_svm},
        "svm_od_forecast": {
            "forecast_do_mg_l": forecast,
            "target_time": "2026-08-26T10:00:00+00:00",
            "asset_id": "ASSET-OD-1",
            "asset_version": "v1",
            "metrics": {"mae": 0.21},
        },
        "warnings": ["La evidencia se conserva como observacion tecnica."],
        "models": [
            {
                "code": WATER_QUALITY_ICA_MODEL_CODE,
                "status": "calculado",
                "current_value": 61.5,
                "unit": "/100",
                "chart": {"series": []},
                "formula": {"latex": r"\\mathrm{ICA}=0.25Q_T+0.25Q_{pH}+0.35Q_{OD}+0.15Q_{NO_3}"},
                "usage": {"status": "en_uso"},
            },
            {
                "code": GROWTH_MODEL_CODE,
                "status": "calculado",
                "current_value": 0.94,
                "unit": "mm/dia",
                "forecast": [{"value": 0.94}],
                "chart": {"series": []},
            },
            {
                "code": SVM_MODEL_CODE,
                "status": "asset_activo" if active_svm else "candidato_bloqueado",
                "current_value": 5.0,
                "unit": "mg/L",
                "asset_id": "ASSET-OD-1",
                "version": "v1",
                "metrics": {"mae": 0.21},
                "chart": {"series": []},
                "formula": {"latex": r"\\widehat{OD}_{t+1h}=SVR(X_t)"},
                "usage": {"status": "en_uso" if active_svm else "candidato_bloqueado"},
            },
        ],
    }


def test_contract_keeps_draft_policy_non_productive() -> None:
    service = ModelAlertDashboardService(object())

    result = service.build_contract(_dashboard(active_svm=True), "LEGACY-POND-1", 24)

    svm = next(model for model in result["models"] if model["code"] == SVM_MODEL_CODE)
    assert len(result["models"]) == 4
    assert svm["maturity"] == "ready_for_policy"
    assert svm["can_emit"] is False
    assert result["events"] == []
    assert result["technical_observations"][0]["productive"] is False


def test_contract_emits_only_with_active_asset_and_approved_policy() -> None:
    service = ModelAlertDashboardService(object())
    policies = {
        SVM_MODEL_CODE: {
            "code": "OD-SVM-LOW-1H",
            "status": "approved",
            "operator": "lte",
            "threshold": 5.0,
            "unit": "mg/L",
            "severity": "advertencia",
            "version": 1,
        }
    }

    result = service.build_contract(_dashboard(active_svm=True, forecast=4.2), "LEGACY-POND-1", 24, policies)

    svm = next(model for model in result["models"] if model["code"] == SVM_MODEL_CODE)
    assert svm["maturity"] == "active"
    assert svm["can_emit"] is True
    assert len(result["events"]) == 1
    assert result["events"][0]["productive"] is True
    assert result["events"][0]["model"]["code"] == SVM_MODEL_CODE
    assert result["events"][0]["policy"]["code"] == "OD-SVM-LOW-1H"


def test_light_context_uses_real_local_measurements_without_calling_it_a_model() -> None:
    now = datetime.now(timezone.utc)
    store = SimpleNamespace(
        list_sensors=lambda _: [
            SimpleNamespace(sensor_code="LUX-01", variable_code="underwater_illuminance_lux"),
        ],
        list_clean_measurements=lambda _, limit: [
            SimpleNamespace(
                variable_code="underwater_illuminance_lux",
                clean_value=315.0,
                time=now,
                standard_unit="lux",
            ),
        ],
    )
    service = ModelAlertDashboardService(store)

    result = service.build_contract(_dashboard(), "LEGACY-POND-1", 24)

    light = result["light"]
    card = next(model for model in result["models"] if model["code"] == "LIGHT_FEED_RESPONSE_CLASSIFIER_V1")
    assert light["sensor_registered"] is True
    assert light["latest_value"] == 315.0
    assert light["chart"]["series"][0]["data"]
    assert card["can_emit"] is False
    assert card["maturity"] == "collecting_data"


def test_alert_endpoint_returns_warmup_contract_without_waiting_for_training_data() -> None:
    ModelAlertDashboardService.clear_cache()
    started = Event()
    release = Event()

    def slow_dashboard(_: str, __: int) -> dict[str, object]:
        started.set()
        release.wait(timeout=2)
        return _dashboard()

    service = ModelAlertDashboardService(object(), dashboard_provider=slow_dashboard)

    payload = service.dashboard("LEGACY-POND-1", 24)

    assert payload["meta"]["warming"] is True
    assert len(payload["models"]) == 4
    assert started.wait(timeout=1)
    release.set()
