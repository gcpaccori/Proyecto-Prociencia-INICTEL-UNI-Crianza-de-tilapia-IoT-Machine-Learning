from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.domains.decision.schemas import AlertDraft
from backend.app.models_engine.base import ModelInputValue, ModelOutput


class DigitalTwinState(BaseModel):
    pond_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    water_quality_current: dict[str, ModelInputValue] = Field(default_factory=dict)
    sensor_timeseries: list[dict[str, object]] = Field(default_factory=list)
    biomass_current: dict[str, ModelInputValue] = Field(default_factory=dict)
    feeding_current: dict[str, object] = Field(default_factory=dict)
    mortality_current: dict[str, object] = Field(default_factory=dict)
    sensor_status: dict[str, object] = Field(default_factory=dict)
    operational_events: list[dict[str, object]] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    risk_code: str
    risk_level: str
    risk_score: float | None = Field(default=None, ge=0.0, le=1.0)
    source: str
    explanation: str
    evidence: dict[str, object] = Field(default_factory=dict)


class Recommendation(BaseModel):
    recommendation_code: str
    priority: str
    recommended_action: str
    explanation: str
    approval_required: bool = True
    source_risk_code: str | None = None
    evidence: dict[str, object] = Field(default_factory=dict)


class DigitalTwinSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: f"DT-SNAPSHOT-{uuid4()}")
    pond_id: str
    timestamp: datetime
    current_state: DigitalTwinState
    model_outputs: list[ModelOutput] = Field(default_factory=list)
    risk_assessments: list[RiskAssessment] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    alerts: list[AlertDraft] = Field(default_factory=list)
    state_summary: dict[str, object] = Field(default_factory=dict)
    data_quality_report: dict[str, object] = Field(default_factory=dict)
    missing_data_report: dict[str, object] = Field(default_factory=dict)
    traceability: dict[str, object] = Field(default_factory=dict)
