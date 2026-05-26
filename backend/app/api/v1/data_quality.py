from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.v1.dependencies import get_store
from backend.app.application import InMemoryBackendStore
from backend.app.application.ml_lifecycle import MLLifecycleService
from backend.app.domains.ml_lifecycle import CleaningRunRead, CleaningRunRequest

router = APIRouter()


def _service(store: InMemoryBackendStore) -> MLLifecycleService:
    return MLLifecycleService(store)


@router.post(
    "/data/cleaning-runs",
    response_model=CleaningRunRead,
    status_code=status.HTTP_201_CREATED,
)
def create_cleaning_run(
    request: CleaningRunRequest,
    store: InMemoryBackendStore = Depends(get_store),
) -> CleaningRunRead:
    try:
        return _service(store).run_cleaning(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/data/cleaning-runs", response_model=list[CleaningRunRead])
def list_cleaning_runs(
    store: InMemoryBackendStore = Depends(get_store),
) -> list[CleaningRunRead]:
    return store.list_cleaning_runs()


@router.get("/data/cleaning-runs/{run_id}", response_model=CleaningRunRead)
def get_cleaning_run(
    run_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> CleaningRunRead:
    run = store.get_cleaning_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cleaning run not found")
    return run


@router.get("/data/cleaning-runs/{run_id}/summary")
def get_cleaning_run_summary(
    run_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> dict[str, object]:
    run = store.get_cleaning_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cleaning run not found")
    return {
        "run_id": run.run_id,
        "status": run.status,
        "records_in": run.records_in,
        "records_out": run.records_out,
        "interpolated_points": run.interpolated_points,
        "outliers_detected": run.outliers_detected,
        "normalized_points": run.normalized_points,
        "steps": [step.model_dump(mode="json") for step in run.steps],
    }


@router.get("/data/cleaning-runs/{run_id}/preview")
def get_cleaning_run_preview(
    run_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> dict[str, object]:
    try:
        return _service(store).cleaning_preview(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
