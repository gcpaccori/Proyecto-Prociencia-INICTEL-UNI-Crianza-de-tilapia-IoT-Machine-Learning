from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.v1.dependencies import get_store
from backend.app.application import InMemoryBackendStore
from backend.app.application.ml_lifecycle import MLLifecycleService
from backend.app.domains.ml_lifecycle import (
    DatasetCoverage,
    DatasetReadiness,
    DatasetSource,
)

router = APIRouter()


def _service(store: InMemoryBackendStore) -> MLLifecycleService:
    return MLLifecycleService(store)


@router.get("/datasets/sources", response_model=list[DatasetSource])
def list_dataset_sources(
    store: InMemoryBackendStore = Depends(get_store),
) -> list[DatasetSource]:
    return _service(store).list_sources()


@router.post("/datasets/sync-legacy")
def sync_legacy_dataset(
    store: InMemoryBackendStore = Depends(get_store),
) -> dict[str, object]:
    return _service(store).sync_legacy()


@router.get("/datasets/coverage", response_model=DatasetCoverage)
def get_dataset_coverage(
    pond_id: str | None = Query(default=None),
    store: InMemoryBackendStore = Depends(get_store),
) -> DatasetCoverage:
    return _service(store).coverage(pond_id=pond_id)


@router.get("/datasets/readiness", response_model=DatasetReadiness)
def get_dataset_readiness(
    model_code: str,
    pond_id: str | None = Query(default=None),
    store: InMemoryBackendStore = Depends(get_store),
) -> DatasetReadiness:
    return _service(store).readiness(model_code=model_code, pond_id=pond_id)


@router.get("/datasets/variables")
def get_dataset_variables(
    pond_id: str | None = Query(default=None),
    store: InMemoryBackendStore = Depends(get_store),
) -> dict[str, object]:
    coverage = _service(store).coverage(pond_id=pond_id)
    return {
        "pond_id": pond_id,
        "variables": [variable.model_dump(mode="json") for variable in coverage.variables],
    }


@router.get("/datasets/timeseries")
def get_dataset_timeseries(
    pond_id: str,
    variable_code: str,
    limit: int = Query(default=500, ge=1, le=100000),
    store: InMemoryBackendStore = Depends(get_store),
) -> dict[str, object]:
    rows = store.list_clean_measurements(
        pond_id=pond_id,
        variable_code=variable_code,
        limit=limit,
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="timeseries not found",
        )
    return {
        "pond_id": pond_id,
        "variable_code": variable_code,
        "points": [row.model_dump(mode="json") for row in rows],
    }
