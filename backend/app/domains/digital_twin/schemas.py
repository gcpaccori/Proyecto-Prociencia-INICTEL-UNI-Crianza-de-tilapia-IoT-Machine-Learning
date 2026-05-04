from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.models_engine.base import ModelInput


class DigitalTwinSnapshotCreate(BaseModel):
    timestamp: datetime | None = None
    state_overrides: dict[str, object] = Field(default_factory=dict)
    model_inputs: dict[str, ModelInput] = Field(default_factory=dict)
    operational_constraints: dict[str, object] = Field(default_factory=dict)
