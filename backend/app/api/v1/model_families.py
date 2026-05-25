from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.v1.dependencies import get_model_catalog_service, get_store
from backend.app.application import InMemoryBackendStore, ModelCatalogService
from backend.app.domains.measurements import (
    CleanMeasurementRead,
    MeasurementIngestionResult,
    RawMeasurementCreate,
    RawMeasurementRead,
)
from backend.app.domains.models import ModelRunRequest
from backend.app.models_engine.base import ModelOutput
from backend.app.models_engine.orchestrators.schemas import Recommendation

router = APIRouter()


def _run_model(
    model_code: str,
    payload: ModelRunRequest,
    catalog: ModelCatalogService,
    store: InMemoryBackendStore,
) -> ModelOutput:
    try:
        output = catalog.run_model(model_code, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return store.save_model_output(output)


@router.post("/models/do/simulate-0d", response_model=ModelOutput)
def simulate_do_0d(
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    return _run_model("DO_DYNAMIC_0D_ROYER_2021", payload, catalog, store)


@router.post("/models/do/simulate-1d", response_model=ModelOutput)
def simulate_do_1d(
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    return _run_model("DO_TRANSPORT_1D", payload, catalog, store)


@router.post("/models/deterministic/oxygen/0d/simulate", response_model=ModelOutput)
def simulate_do_0d_classified(
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    return _run_model("DO_DYNAMIC_0D_ROYER_2021", payload, catalog, store)


@router.post("/models/deterministic/oxygen/1d/simulate", response_model=ModelOutput)
def simulate_do_1d_classified(
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    return _run_model("DO_TRANSPORT_1D", payload, catalog, store)


@router.post("/models/deterministic/ras/oxygen-balance", response_model=ModelOutput)
def ras_oxygen(
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    return _run_model("RAS_OXYGEN_BALANCE", payload, catalog, store)


@router.post("/models/growth/yi/simulate", response_model=ModelOutput)
def yi_growth(
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    return _run_model("YI_ENVIRONMENTAL_GROWTH", payload, catalog, store)


@router.post("/models/growth/soderberg", response_model=ModelOutput)
def soderberg_growth(
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    return _run_model("SODERBERG_LINEAR_GROWTH", payload, catalog, store)


@router.post("/models/growth/zootechnics/calculate", response_model=ModelOutput)
def zootechnics(
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    return _run_model("ZOOTECHNIC_INDEXES", payload, catalog, store)


@router.post("/models/growth/brigolin", response_model=ModelOutput)
def brigolin_growth(
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    return _run_model("BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010", payload, catalog, store)


@router.post("/models/bioenergetic/brigolin/simulate", response_model=ModelOutput)
def brigolin_growth_classified(
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    return _run_model("BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010", payload, catalog, store)


@router.post("/models/feeding/daily-ration/calculate", response_model=ModelOutput)
def daily_ration(
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    return _run_model("DAILY_RATION_MODEL", payload, catalog, store)


@router.post("/models/feeding/satiety/evaluate", response_model=ModelOutput)
def feeding_satiety(
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    return _run_model("FEEDING_SATIETY_RULES", payload, catalog, store)


@router.post("/models/feed/bpnn/predict", response_model=ModelOutput)
def bpnn_feed_intake(
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    return _run_model("BPNN_MEA_FEED_INTAKE", payload, catalog, store)


@router.post("/models/ml/feed-intake/predict", response_model=ModelOutput)
def bpnn_feed_intake_classified(
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    return _run_model("BPNN_MEA_FEED_INTAKE", payload, catalog, store)


@router.post("/models/water-quality/lstm/predict", response_model=ModelOutput)
def water_quality_lstm(
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    return _run_model("PEARSON_LSTM_ATTENTION_WQ", payload, catalog, store)


@router.post("/models/ml/water-quality/forecast", response_model=ModelOutput)
def water_quality_lstm_classified(
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    return _run_model("PEARSON_LSTM_ATTENTION_WQ", payload, catalog, store)


@router.post(
    "/telemetry/ingest",
    response_model=MeasurementIngestionResult,
    status_code=status.HTTP_201_CREATED,
)
def ingest_telemetry(
    payload: RawMeasurementCreate,
    store: InMemoryBackendStore = Depends(get_store),
) -> MeasurementIngestionResult:
    try:
        return store.ingest_measurement(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/telemetry/raw", response_model=list[RawMeasurementRead])
def list_raw_telemetry(
    pond_id: str | None = Query(default=None),
    variable_code: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    store: InMemoryBackendStore = Depends(get_store),
) -> list[RawMeasurementRead]:
    return store.list_raw_measurements(pond_id=pond_id, variable_code=variable_code, limit=limit)


@router.get("/telemetry/clean", response_model=list[CleanMeasurementRead])
def list_clean_telemetry(
    pond_id: str | None = Query(default=None),
    variable_code: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    store: InMemoryBackendStore = Depends(get_store),
) -> list[CleanMeasurementRead]:
    return store.list_clean_measurements(pond_id=pond_id, variable_code=variable_code, limit=limit)


@router.get("/telemetry/timeseries", response_model=list[CleanMeasurementRead])
def list_telemetry_timeseries(
    pond_id: str,
    variable_code: str = Query(default="water_temperature_c"),
    limit: int = Query(default=288, ge=1, le=5000),
    store: InMemoryBackendStore = Depends(get_store),
) -> list[CleanMeasurementRead]:
    rows = store.list_clean_measurements(
        pond_id=pond_id,
        variable_code=variable_code,
        limit=limit,
    )
    return sorted(rows, key=lambda row: row.time)


@router.get("/twin/state/{pond_id}")
def twin_state_alias(
    pond_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> dict[str, object]:
    latest = store.latest_clean_by_variable(pond_id)
    return {
        "pond_id": pond_id,
        "water_quality_current": {
            variable_code: row.model_dump(mode="json")
            for variable_code, row in latest.items()
        },
    }


@router.post("/twin/prescription/recommend", response_model=list[Recommendation])
def twin_prescription_recommend(
    pond_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> list[Recommendation]:
    latest = store.latest_snapshot(pond_id)
    return latest.recommendations if latest else []
