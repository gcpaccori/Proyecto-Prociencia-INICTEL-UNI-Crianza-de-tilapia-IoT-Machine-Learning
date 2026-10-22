from fastapi import APIRouter

from backend.app.api.v1.actuation import router as actuation_router
from backend.app.api.v1.aquaculture import router as aquaculture_router
from backend.app.api.v1.data_quality import router as data_quality_router
from backend.app.api.v1.datasets import router as datasets_router
from backend.app.api.v1.decision import router as decision_router
from backend.app.api.v1.digital_twin import router as digital_twin_router
from backend.app.api.v1.features import router as features_router
from backend.app.api.v1.frontend import router as frontend_router
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.measurements import router as measurements_router
from backend.app.api.v1.ml_lifecycle import router as ml_lifecycle_router
from backend.app.api.v1.model_families import router as model_families_router
from backend.app.api.v1.models import router as models_router
from backend.app.api.v1.real_models import router as real_models_router
from backend.app.api.v1.tilapia_growth_ml import router as tilapia_growth_ml_router
from backend.app.api.v1.tilapia_growth_adaptive import router as tilapia_growth_adaptive_router
from backend.app.api.v1.tilapia_sensor_forecast import router as tilapia_sensor_forecast_router
from backend.app.api.v1.direct_sensor_growth import router as direct_sensor_growth_router
from backend.app.api.v1.gaussian_tilapia_growth import router as gaussian_tilapia_growth_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(aquaculture_router, tags=["aquaculture"])
api_router.include_router(measurements_router, tags=["measurements"])
api_router.include_router(datasets_router, tags=["datasets"])
api_router.include_router(data_quality_router, tags=["data-quality"])
api_router.include_router(features_router, tags=["features"])
api_router.include_router(ml_lifecycle_router, tags=["ml-lifecycle"])
api_router.include_router(models_router, tags=["models"])
api_router.include_router(real_models_router, tags=["real-models"])
api_router.include_router(tilapia_growth_ml_router, tags=["supervised-growth-ml"])
api_router.include_router(tilapia_growth_adaptive_router, tags=["adaptive-growth-ml"])
api_router.include_router(tilapia_sensor_forecast_router, tags=["experimental-tilapia-sensors"])
api_router.include_router(direct_sensor_growth_router, tags=["experimental-direct-growth"])
api_router.include_router(gaussian_tilapia_growth_router, tags=["experimental-gaussian-growth"])
api_router.include_router(model_families_router, tags=["model-families"])
api_router.include_router(frontend_router, tags=["frontend"])
api_router.include_router(digital_twin_router, tags=["digital-twin"])
api_router.include_router(decision_router, tags=["decision"])
api_router.include_router(actuation_router, tags=["actuation"])
