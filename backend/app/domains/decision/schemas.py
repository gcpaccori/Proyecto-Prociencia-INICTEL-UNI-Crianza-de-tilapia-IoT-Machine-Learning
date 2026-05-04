from datetime import datetime, timezone

from pydantic import BaseModel, Field


class AlertDraft(BaseModel):
    alert_code: str
    severity: str
    status: str = "open"
    message: str
    source_risk_code: str | None = None
    source_recommendation_code: str | None = None
    evidence: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AlertRead(AlertDraft):
    id: str
    snapshot_id: str
    pond_id: str


class RecommendationRead(BaseModel):
    id: str
    snapshot_id: str
    pond_id: str
    recommendation_code: str
    priority: str
    recommended_action: str
    explanation: str
    approval_required: bool = True
    source_risk_code: str | None = None
    evidence: dict[str, object] = Field(default_factory=dict)
