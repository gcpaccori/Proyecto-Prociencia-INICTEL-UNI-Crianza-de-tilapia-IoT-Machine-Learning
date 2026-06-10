from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.models_engine.base import ModelInput


class DigitalTwinSnapshotCreate(BaseModel):
    timestamp: datetime | None = None
    state_overrides: dict[str, object] = Field(default_factory=dict)
    model_inputs: dict[str, ModelInput] = Field(default_factory=dict)
    operational_constraints: dict[str, object] = Field(default_factory=dict)


class DigitalTwinProjectionRequest(BaseModel):
    horizon_hours: int = Field(default=24, ge=1, le=720)
    step_hours: int = Field(default=1, ge=1, le=24)
    selected_models: list[str] = Field(default_factory=list)
    variable_adjustments_per_hour: dict[str, float] = Field(default_factory=dict)
    operational_controls: dict[str, float | bool | str] = Field(default_factory=dict)


class DigitalTwinProjectionPoint(BaseModel):
    timestamp: datetime
    hour: int
    values: dict[str, float] = Field(default_factory=dict)
    provenance: dict[str, str] = Field(default_factory=dict)
    model_activity: dict[str, float] = Field(default_factory=dict)
    biological_state: dict[str, float | str] = Field(default_factory=dict)
    operational_state: dict[str, float | str] = Field(default_factory=dict)


class DigitalTwinModelParticipation(BaseModel):
    model_code: str
    status: str
    impact_variables: list[str] = Field(default_factory=list)
    influence_weight: float = 0.0
    explanation: str
    asset_id: str | None = None


class DigitalTwinProjectionResponse(BaseModel):
    pond_id: str
    generated_at: datetime
    horizon_hours: int
    step_hours: int
    baseline_values: dict[str, float] = Field(default_factory=dict)
    baseline_observed_at: dict[str, datetime] = Field(default_factory=dict)
    baseline_ingested_at: dict[str, datetime] = Field(default_factory=dict)
    baseline_units: dict[str, str] = Field(default_factory=dict)
    baseline_quality_flags: dict[str, str] = Field(default_factory=dict)
    observed_trends_per_hour: dict[str, float] = Field(default_factory=dict)
    scenario_adjustments_per_hour: dict[str, float] = Field(default_factory=dict)
    operational_controls: dict[str, float | bool | str] = Field(default_factory=dict)
    initial_productive_state: dict[str, float | str] = Field(default_factory=dict)
    simulation_summary: dict[str, float | str] = Field(default_factory=dict)
    derived_indicators: dict[str, float | str] = Field(default_factory=dict)
    simulation_assumptions: dict[str, float | str] = Field(default_factory=dict)
    points: list[DigitalTwinProjectionPoint] = Field(default_factory=list)
    model_participation: list[DigitalTwinModelParticipation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    traceability: dict[str, object] = Field(default_factory=dict)
