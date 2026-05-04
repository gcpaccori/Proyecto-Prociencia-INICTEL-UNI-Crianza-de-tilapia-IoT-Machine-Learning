from datetime import datetime, timezone

from pydantic import BaseModel, Field

from backend.app.models_engine.base import ModelInputValue


class ModelCatalogItem(BaseModel):
    model_code: str
    model_version: str
    model_type: str
    name: str
    source_report: str
    source_reference: str | None = None
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    readiness_status: str


class ModelRunRequest(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pond_id: str | None = None
    farm_id: str | None = None
    inputs: dict[str, ModelInputValue]
    parameters: dict[str, object] = Field(default_factory=dict)
