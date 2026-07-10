from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend.app.api.v1.dependencies import get_store
from backend.app.application.real_models import RealModelsService


router = APIRouter()


class DynamicOxygenRequest(BaseModel):
    flow_rate_l_h: float | None = None
    raceway_volume_l: float | None = None
    do_influent_mg_l: float | None = None
    oxygen_supply_rate_mg_l_h: float | None = None
    fish_biomass_kg: float | None = None
    fish_respiration_rate_mg_h_kg: float | None = None
    reaeration_rate_h_1: float | None = None
    dt_h: float | None = None


def _service(store: object) -> RealModelsService:
    return RealModelsService(store)


def _legacy_pond_id(pond_id: str) -> str:
    return f"LEGACY-POND-{pond_id}" if pond_id.isdigit() else pond_id


def _run(callable_: object) -> dict[str, object]:
    try:
        return callable_()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post("/ponds/{pond_id}/models/svm-od/train", status_code=status.HTTP_201_CREATED)
def train_svm_od(pond_id: str, store: object = Depends(get_store)) -> dict[str, object]:
    return _run(lambda: _service(store).train_svm_od(_legacy_pond_id(pond_id)))


@router.post("/ponds/{pond_id}/models/svm-od/forecast")
def forecast_svm_od(pond_id: str, store: object = Depends(get_store)) -> dict[str, object]:
    return _run(lambda: _service(store).forecast_svm_od(_legacy_pond_id(pond_id)))


@router.get("/ponds/{pond_id}/models/svm-od/metrics")
def svm_od_metrics(pond_id: str, store: object = Depends(get_store)) -> dict[str, object]:
    return _run(lambda: _service(store).svm_metrics(_legacy_pond_id(pond_id)))


@router.get("/ponds/{pond_id}/models/oxygen/status")
def get_oxygen_status(pond_id: str, store: object = Depends(get_store)) -> dict[str, object]:
    return _run(lambda: _service(store).oxygen_status_for_pond(_legacy_pond_id(pond_id)))


@router.post("/ponds/{pond_id}/models/oxygen/dynamic")
def run_dynamic_oxygen(
    pond_id: str,
    request: DynamicOxygenRequest,
    store: object = Depends(get_store),
) -> dict[str, object]:
    return _run(
        lambda: _service(store).dynamic_oxygen(
            _legacy_pond_id(pond_id),
            request.model_dump(),
        )
    )


@router.get("/ponds/{pond_id}/models/tilapia-growth")
def get_tilapia_growth(
    pond_id: str,
    projection_days: int | None = Query(default=None, ge=1, le=365),
    store: object = Depends(get_store),
) -> dict[str, object]:
    return _run(
        lambda: _service(store).tilapia_growth(
            _legacy_pond_id(pond_id),
            projection_days=projection_days,
        )
    )


@router.get("/ponds/{pond_id}/ai/dashboard")
def get_ai_dashboard(pond_id: str, store: object = Depends(get_store)) -> dict[str, object]:
    return _run(lambda: _service(store).dashboard(_legacy_pond_id(pond_id)))
