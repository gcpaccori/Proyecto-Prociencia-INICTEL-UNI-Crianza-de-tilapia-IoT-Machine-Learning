from fastapi import FastAPI

from backend.app.api.v1.router import api_router
from backend.app.application import (
    DigitalTwinApplicationService,
    InMemoryBackendStore,
    ModelCatalogService,
)
from backend.app.core.config import Settings, get_settings
from backend.app.core.exceptions import register_exception_handlers
from backend.app.core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)

    docs_url = "/docs" if app_settings.enable_docs else None
    redoc_url = "/redoc" if app_settings.enable_docs else None
    openapi_url = "/openapi.json" if app_settings.enable_docs else None

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    app.state.settings = app_settings
    app.state.backend_store = InMemoryBackendStore()
    app.state.model_catalog_service = ModelCatalogService()
    app.state.digital_twin_service = DigitalTwinApplicationService(
        app.state.backend_store,
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=app_settings.api_v1_prefix)

    return app


app = create_app()
