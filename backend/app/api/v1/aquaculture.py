from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.v1.dependencies import get_store
from backend.app.application import InMemoryBackendStore
from backend.app.domains.aquaculture import (
    FarmCreate,
    FarmRead,
    PondCreate,
    PondRead,
    SensorCreate,
    SensorRead,
)

router = APIRouter()


@router.post("/farms", response_model=FarmRead, status_code=status.HTTP_201_CREATED)
def create_farm(
    payload: FarmCreate,
    store: InMemoryBackendStore = Depends(get_store),
) -> FarmRead:
    try:
        return store.create_farm(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/farms", response_model=list[FarmRead])
def list_farms(store: InMemoryBackendStore = Depends(get_store)) -> list[FarmRead]:
    return store.list_farms()


@router.get("/farms/{farm_id}", response_model=FarmRead)
def get_farm(
    farm_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> FarmRead:
    farm = store.get_farm(farm_id)
    if farm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="farm not found")
    return farm


@router.post("/ponds", response_model=PondRead, status_code=status.HTTP_201_CREATED)
def create_pond(
    payload: PondCreate,
    store: InMemoryBackendStore = Depends(get_store),
) -> PondRead:
    try:
        return store.create_pond(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/ponds", response_model=list[PondRead])
def list_ponds(
    farm_id: str | None = Query(default=None),
    store: InMemoryBackendStore = Depends(get_store),
) -> list[PondRead]:
    return store.list_ponds(farm_id=farm_id)


@router.get("/ponds/{pond_id}", response_model=PondRead)
def get_pond(
    pond_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> PondRead:
    pond = store.get_pond(pond_id)
    if pond is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="pond not found")
    return pond


@router.post("/sensors", response_model=SensorRead, status_code=status.HTTP_201_CREATED)
def create_sensor(
    payload: SensorCreate,
    store: InMemoryBackendStore = Depends(get_store),
) -> SensorRead:
    try:
        return store.create_sensor(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/sensors", response_model=list[SensorRead])
def list_sensors(
    pond_id: str | None = Query(default=None),
    store: InMemoryBackendStore = Depends(get_store),
) -> list[SensorRead]:
    return store.list_sensors(pond_id=pond_id)


@router.get("/sensors/{sensor_id}", response_model=SensorRead)
def get_sensor(
    sensor_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> SensorRead:
    sensor = store.get_sensor(sensor_id)
    if sensor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sensor not found")
    return sensor
