from fastapi import Request

from backend.app.application import (
    DigitalTwinApplicationService,
    InMemoryBackendStore,
    ModelCatalogService,
)


def get_store(request: Request) -> InMemoryBackendStore:
    return request.app.state.backend_store


def get_digital_twin_service(request: Request) -> DigitalTwinApplicationService:
    return request.app.state.digital_twin_service


def get_model_catalog_service(request: Request) -> ModelCatalogService:
    return request.app.state.model_catalog_service
