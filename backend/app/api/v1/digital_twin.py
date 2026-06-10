from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.v1.dependencies import get_digital_twin_service, get_store
from backend.app.application import DigitalTwinApplicationService, InMemoryBackendStore
from backend.app.domains.digital_twin import (
    DigitalTwinProjectionRequest,
    DigitalTwinProjectionResponse,
    DigitalTwinSnapshotCreate,
    RasOperationalEventCreate,
    RasOperationalEventRead,
)
from backend.app.models_engine.orchestrators.schemas import (
    DigitalTwinSnapshot,
    DigitalTwinState,
    Recommendation,
    RiskAssessment,
)

router = APIRouter()


@router.post(
    "/digital-twin/{pond_id}/events",
    response_model=RasOperationalEventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_ras_operational_event(
    pond_id: str,
    payload: RasOperationalEventCreate,
    store: InMemoryBackendStore = Depends(get_store),
) -> RasOperationalEventRead:
    return store.save_ras_operational_event(pond_id, payload)


@router.get(
    "/digital-twin/{pond_id}/events",
    response_model=list[RasOperationalEventRead],
)
def list_ras_operational_events(
    pond_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    store: InMemoryBackendStore = Depends(get_store),
) -> list[RasOperationalEventRead]:
    return store.list_ras_operational_events(pond_id, limit)


@router.get("/ponds/{pond_id}/state", response_model=DigitalTwinState)
def get_pond_state(
    pond_id: str,
    service: DigitalTwinApplicationService = Depends(get_digital_twin_service),
) -> DigitalTwinState:
    return service.load_state(pond_id)


@router.post(
    "/digital-twin/{pond_id}/projection",
    response_model=DigitalTwinProjectionResponse,
)
def project_digital_twin_scenario(
    pond_id: str,
    payload: DigitalTwinProjectionRequest,
    service: DigitalTwinApplicationService = Depends(get_digital_twin_service),
) -> DigitalTwinProjectionResponse:
    return service.project_scenario(pond_id, payload)


@router.post(
    "/digital-twin/{pond_id}/snapshot",
    response_model=DigitalTwinSnapshot,
    status_code=status.HTTP_201_CREATED,
)
def create_snapshot(
    pond_id: str,
    payload: DigitalTwinSnapshotCreate | None = None,
    service: DigitalTwinApplicationService = Depends(get_digital_twin_service),
) -> DigitalTwinSnapshot:
    request = payload or DigitalTwinSnapshotCreate()
    return service.create_snapshot(
        pond_id=pond_id,
        timestamp=request.timestamp,
        state_overrides=request.state_overrides,
        model_inputs=request.model_inputs,
        operational_constraints=request.operational_constraints,
    )


@router.post(
    "/digital-twin/{pond_id}/snapshots",
    response_model=DigitalTwinSnapshot,
    status_code=status.HTTP_201_CREATED,
)
def create_snapshot_by_body(
    pond_id: str,
    payload: DigitalTwinSnapshotCreate,
    service: DigitalTwinApplicationService = Depends(get_digital_twin_service),
) -> DigitalTwinSnapshot:
    return service.create_snapshot(
        pond_id=pond_id,
        timestamp=payload.timestamp,
        state_overrides=payload.state_overrides,
        model_inputs=payload.model_inputs,
        operational_constraints=payload.operational_constraints,
    )


@router.get("/digital-twin/snapshots/{snapshot_id}", response_model=DigitalTwinSnapshot)
def get_snapshot(
    snapshot_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> DigitalTwinSnapshot:
    snapshot = store.get_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="snapshot not found",
        )
    return snapshot


@router.get("/digital-twin/{pond_id}/latest", response_model=DigitalTwinSnapshot)
def get_latest_snapshot(
    pond_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> DigitalTwinSnapshot:
    snapshot = store.latest_snapshot(pond_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="snapshot not found",
        )
    return snapshot


@router.get("/digital-twin/{pond_id}/risks", response_model=list[RiskAssessment])
def list_latest_risks(
    pond_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> list[RiskAssessment]:
    snapshot = store.latest_snapshot(pond_id)
    if snapshot is None:
        return []
    return snapshot.risk_assessments


@router.get(
    "/digital-twin/{pond_id}/recommendations",
    response_model=list[Recommendation],
)
def list_latest_recommendations(
    pond_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> list[Recommendation]:
    snapshot = store.latest_snapshot(pond_id)
    if snapshot is None:
        return []
    return snapshot.recommendations
