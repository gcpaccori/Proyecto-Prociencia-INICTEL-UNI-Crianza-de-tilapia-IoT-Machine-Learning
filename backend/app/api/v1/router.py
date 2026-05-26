from fastapi import APIRouter

from backend.app.api.v1.actuation import router as actuation_router
from backend.app.api.v1.aquaculture import router as aquaculture_router
from backend.app.api.v1.decision import router as decision_router
from backend.app.api.v1.digital_twin import router as digital_twin_router
from backend.app.api.v1.frontend import router as frontend_router
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.measurements import router as measurements_router
from backend.app.api.v1.model_families import router as model_families_router
from backend.app.api.v1.models import router as models_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(aquaculture_router, tags=["aquaculture"])
api_router.include_router(measurements_router, tags=["measurements"])
api_router.include_router(models_router, tags=["models"])
api_router.include_router(model_families_router, tags=["model-families"])
api_router.include_router(frontend_router, tags=["frontend"])
api_router.include_router(digital_twin_router, tags=["digital-twin"])
api_router.include_router(decision_router, tags=["decision"])
api_router.include_router(actuation_router, tags=["actuation"])
