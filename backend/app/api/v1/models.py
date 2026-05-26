from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.v1.dependencies import get_model_catalog_service, get_store
from backend.app.application import InMemoryBackendStore, ModelCatalogService
from backend.app.domains.models import (
    ModelBatchTestRun,
    ModelCatalogItem,
    ModelInputAudit,
    ModelRunRequest,
    ModelTestRunItem,
    ModelTestPayload,
)
from backend.app.models_engine.base import ModelOutput

router = APIRouter()


@router.get("/models", response_model=list[ModelCatalogItem])
def list_models(
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
) -> list[ModelCatalogItem]:
    return catalog.list_models()


@router.post("/models/test-run-all", response_model=ModelBatchTestRun)
def run_all_models_with_test_payloads(
    pond_id: str | None = None,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelBatchTestRun:
    results: list[ModelTestRunItem] = []
    for model in catalog.list_models():
        payload = catalog.build_test_payload(model.model_code, store, pond_id=pond_id)
        if payload is None:
            results.append(
                ModelTestRunItem(
                    model_code=model.model_code,
                    status="failed",
                    readiness_status=model.readiness_status,
                    error="model not found",
                )
            )
            continue
        try:
            output = store.save_model_output(
                catalog.run_model(model.model_code, payload.request)
            )
        except (RuntimeError, ValueError) as exc:
            results.append(
                ModelTestRunItem(
                    model_code=model.model_code,
                    status="failed",
                    readiness_status=payload.readiness_status,
                    auto_input_names=payload.auto_input_names,
                    generated_input_names=payload.generated_input_names,
                    error=str(exc),
                )
            )
            continue
        results.append(
            ModelTestRunItem(
                model_code=model.model_code,
                status="succeeded",
                readiness_status=payload.readiness_status,
                run_id=output.run_id,
                auto_input_names=payload.auto_input_names,
                generated_input_names=payload.generated_input_names,
                warnings=output.warnings,
            )
        )

    failed = sum(1 for result in results if result.status != "succeeded")
    return ModelBatchTestRun(
        pond_id=pond_id,
        total=len(results),
        succeeded=len(results) - failed,
        failed=failed,
        results=results,
    )


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


@router.get("/models/{model_code}/test-payload", response_model=ModelTestPayload)
def get_model_test_payload(
    model_code: str,
    pond_id: str | None = None,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelTestPayload:
    payload = catalog.build_test_payload(model_code, store, pond_id=pond_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model not found")
    return payload


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


@router.post("/models/{model_code}/test-run", response_model=ModelOutput)
def run_model_with_test_payload(
    model_code: str,
    pond_id: str | None = None,
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> ModelOutput:
    payload = catalog.build_test_payload(model_code, store, pond_id=pond_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model not found")
    try:
        output = catalog.run_model(model_code, payload.request)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return store.save_model_output(output)
