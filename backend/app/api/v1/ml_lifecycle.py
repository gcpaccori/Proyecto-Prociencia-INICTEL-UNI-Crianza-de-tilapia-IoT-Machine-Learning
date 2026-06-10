from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.v1.dependencies import get_store
from backend.app.application import InMemoryBackendStore
from backend.app.application.ml_lifecycle import MLLifecycleService
from backend.app.domains.ml_lifecycle import (
    MLLifecycleStatus,
    ModelAssetPredictionRead,
    ModelAssetPredictionHistoryRead,
    ModelAssetPredictionRequest,
    ModelAssetRead,
    ModelLifecycleDetailRead,
    ModelPortfolioRead,
    TrainableModelRead,
    TrainingJobEventRead,
    TrainingJobRead,
    TrainingJobRequest,
)

router = APIRouter()


def _service(store: InMemoryBackendStore) -> MLLifecycleService:
    return MLLifecycleService(store)


@router.get("/ml/lifecycle/status", response_model=MLLifecycleStatus)
def get_ml_lifecycle_status(
    store: InMemoryBackendStore = Depends(get_store),
) -> MLLifecycleStatus:
    return _service(store).lifecycle_status()


@router.get("/ml/trainable-models", response_model=list[TrainableModelRead])
def list_trainable_models(
    store: InMemoryBackendStore = Depends(get_store),
) -> list[TrainableModelRead]:
    return _service(store).list_trainable_models()


@router.get("/ml/models/portfolio", response_model=list[ModelPortfolioRead])
def get_model_portfolio(
    pond_id: str | None = Query(default=None),
    store: InMemoryBackendStore = Depends(get_store),
) -> list[ModelPortfolioRead]:
    return _service(store).model_portfolio(pond_id=pond_id)


@router.post(
    "/ml/training-jobs",
    response_model=TrainingJobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_training_job(
    request: TrainingJobRequest,
    store: InMemoryBackendStore = Depends(get_store),
) -> TrainingJobRead:
    return _service(store).train(request)


@router.post(
    "/models/{model_code}/train",
    response_model=TrainingJobRead,
    status_code=status.HTTP_201_CREATED,
)
def train_model_alias(
    model_code: str,
    request: TrainingJobRequest,
    store: InMemoryBackendStore = Depends(get_store),
) -> TrainingJobRead:
    return _service(store).train(request.model_copy(update={"model_code": model_code}))


@router.get("/ml/training-jobs", response_model=list[TrainingJobRead])
def list_training_jobs(
    store: InMemoryBackendStore = Depends(get_store),
) -> list[TrainingJobRead]:
    return store.list_training_jobs()


@router.get("/ml/training-jobs/{job_id}", response_model=TrainingJobRead)
def get_training_job(
    job_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> TrainingJobRead:
    job = store.get_training_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="training job not found")
    return job


@router.get("/ml/training-jobs/{job_id}/events", response_model=list[TrainingJobEventRead])
def list_training_job_events(
    job_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> list[TrainingJobEventRead]:
    if store.get_training_job(job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="training job not found")
    return store.list_training_job_events(job_id)


@router.get("/ml/models/{model_code}/lifecycle", response_model=ModelLifecycleDetailRead)
def get_model_lifecycle_detail(
    model_code: str,
    pond_id: str | None = Query(default=None),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelLifecycleDetailRead:
    return _service(store).model_lifecycle_detail(model_code=model_code, pond_id=pond_id)


@router.post("/ml/training-jobs/{job_id}/cancel", response_model=TrainingJobRead)
def cancel_training_job(
    job_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> TrainingJobRead:
    job = store.get_training_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="training job not found")
    if job.status not in {"queued", "running"}:
        return job
    cancelled = job.model_copy(update={"status": "cancelled"})
    return store.save_training_job(cancelled)


@router.get("/ml/model-assets", response_model=list[ModelAssetRead])
def list_model_assets(
    model_code: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    include_payload: bool = Query(default=True),
    store: InMemoryBackendStore = Depends(get_store),
) -> list[ModelAssetRead]:
    assets = store.list_model_assets(model_code=model_code, status=status_filter)
    if include_payload:
        return assets
    return [_summarize_model_asset(asset) for asset in assets]


def _summarize_model_asset(asset: ModelAssetRead) -> ModelAssetRead:
    payload = asset.artifact_payload
    public_payload = {
        key: payload[key]
        for key in ("task", "algorithm", "model_code", "feature_names", "estimator_name", "target_variable")
        if key in payload
    }
    return asset.model_copy(update={"artifact_payload": public_payload})


@router.get("/ml/model-assets/{asset_id}", response_model=ModelAssetRead)
def get_model_asset(
    asset_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelAssetRead:
    asset = store.get_model_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model asset not found")
    return asset


@router.get("/ml/model-assets/{asset_id}/lineage")
def get_model_asset_lineage(
    asset_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> dict[str, object]:
    try:
        return _service(store).model_asset_lineage(asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/ml/predictions", response_model=list[ModelAssetPredictionHistoryRead])
def list_model_predictions(
    model_code: str | None = Query(default=None),
    asset_id: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    store: InMemoryBackendStore = Depends(get_store),
) -> list[ModelAssetPredictionHistoryRead]:
    return _service(store).prediction_history(
        model_code=model_code,
        asset_id=asset_id,
        limit=limit,
    )


@router.post("/ml/model-assets/{asset_id}/activate", response_model=ModelAssetRead)
def activate_model_asset(
    asset_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelAssetRead:
    try:
        return store.activate_model_asset(asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/ml/model-assets/{asset_id}/deprecate", response_model=ModelAssetRead)
def deprecate_model_asset(
    asset_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelAssetRead:
    try:
        return store.deprecate_model_asset(asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/models/{model_code}/asset", response_model=ModelAssetRead | None)
def get_active_model_asset(
    model_code: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelAssetRead | None:
    return store.active_model_asset(model_code)


@router.get("/models/{model_code}/metrics")
def get_model_metrics(
    model_code: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> dict[str, object]:
    active_asset = store.active_model_asset(model_code)
    return {
        "model_code": model_code,
        "active_asset_id": active_asset.asset_id if active_asset else None,
        "metrics": active_asset.metrics_json if active_asset else {},
    }


@router.post(
    "/ml/model-assets/{asset_id}/predict",
    response_model=ModelAssetPredictionRead,
)
def predict_with_model_asset(
    asset_id: str,
    request: ModelAssetPredictionRequest,
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelAssetPredictionRead:
    asset = store.get_model_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model asset not found")
    try:
        return _service(store).predict_with_asset(asset, request.features)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post(
    "/models/{model_code}/predict",
    response_model=ModelAssetPredictionRead,
)
def predict_with_active_model_asset(
    model_code: str,
    request: ModelAssetPredictionRequest,
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelAssetPredictionRead:
    asset = store.active_model_asset(model_code)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="active model asset not found")
    try:
        return _service(store).predict_with_asset(asset, request.features)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
