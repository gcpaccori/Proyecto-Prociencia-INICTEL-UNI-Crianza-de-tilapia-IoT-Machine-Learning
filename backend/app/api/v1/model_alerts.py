from fastapi import APIRouter, Depends, Query

from backend.app.api.v1.dependencies import get_store
from backend.app.application.model_alerts import ModelAlertDashboardService
from backend.app.application.model_validation import build_model_validation


router = APIRouter()


def _legacy_pond_id(pond_id: str) -> str:
    return f"LEGACY-POND-{pond_id}" if pond_id.isdigit() else pond_id


@router.get("/ponds/{pond_id}/model-alerts/dashboard")
def model_alert_dashboard(
    pond_id: str,
    window_hours: int = Query(default=24, ge=6, le=2160),
    store: object = Depends(get_store),
) -> dict[str, object]:
    """Return the local ML-alert contract without blocking the browser request."""
    return ModelAlertDashboardService(store).dashboard(
        _legacy_pond_id(pond_id),
        window_hours=window_hours,
    )


@router.get("/ponds/{pond_id}/model-validation")
def model_validation(
    pond_id: str,
    refresh: bool = Query(default=False),
    store: object = Depends(get_store),
) -> dict[str, object]:
    """Cada modelo contrastado con lo que midieron los sensores, con dispersion y R2."""
    return build_model_validation(store, _legacy_pond_id(pond_id), refresh=refresh)
