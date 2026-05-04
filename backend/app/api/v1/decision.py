from fastapi import APIRouter, Depends, Query

from backend.app.api.v1.dependencies import get_store
from backend.app.application import InMemoryBackendStore
from backend.app.domains.decision import AlertRead, RecommendationRead

router = APIRouter()


@router.get("/alerts", response_model=list[AlertRead])
def list_alerts(
    pond_id: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    store: InMemoryBackendStore = Depends(get_store),
) -> list[AlertRead]:
    return store.list_alerts(pond_id=pond_id, severity=severity)


@router.get("/recommendations", response_model=list[RecommendationRead])
def list_recommendations(
    pond_id: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    store: InMemoryBackendStore = Depends(get_store),
) -> list[RecommendationRead]:
    return store.list_recommendations(pond_id=pond_id, priority=priority)
