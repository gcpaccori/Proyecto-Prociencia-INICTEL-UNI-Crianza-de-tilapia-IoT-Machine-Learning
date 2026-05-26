from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.v1.dependencies import get_store
from backend.app.application import InMemoryBackendStore
from backend.app.application.ml_lifecycle import MLLifecycleService
from backend.app.domains.ml_lifecycle import (
    FeatureBuildRequest,
    FeatureSetPreview,
    FeatureSetRead,
)

router = APIRouter()


def _service(store: InMemoryBackendStore) -> MLLifecycleService:
    return MLLifecycleService(store)


@router.post(
    "/features/build",
    response_model=FeatureSetRead,
    status_code=status.HTTP_201_CREATED,
)
def build_feature_set(
    request: FeatureBuildRequest,
    store: InMemoryBackendStore = Depends(get_store),
) -> FeatureSetRead:
    try:
        return _service(store).build_feature_set(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/features", response_model=list[FeatureSetRead])
def list_feature_sets(
    store: InMemoryBackendStore = Depends(get_store),
) -> list[FeatureSetRead]:
    return store.list_feature_sets()


@router.get("/features/{feature_set_id}", response_model=FeatureSetRead)
def get_feature_set(
    feature_set_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> FeatureSetRead:
    feature_set = store.get_feature_set(feature_set_id)
    if feature_set is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="feature set not found")
    return feature_set


@router.get("/features/{feature_set_id}/preview", response_model=FeatureSetPreview)
def get_feature_set_preview(
    feature_set_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> FeatureSetPreview:
    try:
        return _service(store).feature_preview(feature_set_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/features/{feature_set_id}/columns")
def get_feature_set_columns(
    feature_set_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> dict[str, object]:
    feature_set = store.get_feature_set(feature_set_id)
    if feature_set is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="feature set not found")
    return {
        "feature_set_id": feature_set_id,
        "columns": [column.model_dump(mode="json") for column in feature_set.columns],
    }
