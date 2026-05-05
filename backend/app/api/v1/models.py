from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.v1.dependencies import get_model_catalog_service, get_store
from backend.app.application import InMemoryBackendStore, ModelCatalogService
from backend.app.domains.models import ModelCatalogItem, ModelInputAudit, ModelRunRequest
from backend.app.models_engine.base import ModelOutput

router = APIRouter()


@router.get("/models", response_model=list[ModelCatalogItem])
def list_models(
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
) -> list[ModelCatalogItem]:
    return catalog.list_models()


@router.get("/models/{model_code}", response_model=ModelCatalogItem)
def get_model(
    model_code: str,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
) -> ModelCatalogItem:
    model = catalog.get_model(model_code)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model not found")
    return model


@router.get("/models/{model_code}/input-audit", response_model=ModelInputAudit)
def audit_model_inputs(
    model_code: str,
    pond_id: str | None = None,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelInputAudit:
    audit = catalog.audit_inputs(model_code, store, pond_id=pond_id)
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model not found")
    return audit


@router.post("/models/{model_code}/run", response_model=ModelOutput)
def run_model(
    model_code: str,
    payload: ModelRunRequest,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
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
