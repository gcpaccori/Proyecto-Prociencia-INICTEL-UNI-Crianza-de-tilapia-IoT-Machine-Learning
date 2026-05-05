from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.v1.dependencies import get_store
from backend.app.application import InMemoryBackendStore
from backend.app.domains.measurements import (
    CleanMeasurementRead,
    MeasurementIngestionResult,
    RawMeasurementCreate,
    RawMeasurementRead,
)

router = APIRouter()
DEFAULT_TIMESERIES_VARIABLE_CODE = "water_temperature_c"


@router.post(
    "/measurements/ingest",
    response_model=MeasurementIngestionResult,
    status_code=status.HTTP_201_CREATED,
)
def ingest_measurement(
    payload: RawMeasurementCreate,
    store: InMemoryBackendStore = Depends(get_store),
) -> MeasurementIngestionResult:
    try:
        return store.ingest_measurement(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/measurements/raw", response_model=list[RawMeasurementRead])
def list_raw_measurements(
    pond_id: str | None = Query(default=None),
    variable_code: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    store: InMemoryBackendStore = Depends(get_store),
) -> list[RawMeasurementRead]:
    return store.list_raw_measurements(
        pond_id=pond_id,
        variable_code=variable_code,
        limit=limit,
    )


@router.get("/measurements/clean", response_model=list[CleanMeasurementRead])
def list_clean_measurements(
    pond_id: str | None = Query(default=None),
    variable_code: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    store: InMemoryBackendStore = Depends(get_store),
) -> list[CleanMeasurementRead]:
    return store.list_clean_measurements(
        pond_id=pond_id,
        variable_code=variable_code,
        limit=limit,
    )


@router.get("/ponds/{pond_id}/measurements", response_model=list[CleanMeasurementRead])
def list_pond_measurements(
    pond_id: str,
    variable_code: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    store: InMemoryBackendStore = Depends(get_store),
) -> list[CleanMeasurementRead]:
    return store.list_clean_measurements(
        pond_id=pond_id,
        variable_code=variable_code,
        limit=limit,
    )


@router.get("/ponds/{pond_id}/timeseries", response_model=list[CleanMeasurementRead])
def list_pond_timeseries(
    pond_id: str,
    variable_code: str | None = Query(default=DEFAULT_TIMESERIES_VARIABLE_CODE),
    limit: int = Query(default=288, ge=1, le=5000),
    store: InMemoryBackendStore = Depends(get_store),
) -> list[CleanMeasurementRead]:
    rows = store.list_clean_measurements(
        pond_id=pond_id,
        variable_code=variable_code,
        limit=limit,
    )
    return sorted(rows, key=lambda row: row.time)
