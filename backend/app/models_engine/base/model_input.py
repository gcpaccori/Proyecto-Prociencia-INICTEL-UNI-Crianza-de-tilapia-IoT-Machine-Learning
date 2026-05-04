from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


class ModelInputValue(BaseModel):
    value: object
    unit: str = Field(min_length=1)
    source_measurement_id: UUID | None = None
    quality_flag: str | None = None


class ModelInput(BaseModel):
    model_code: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pond_id: str | None = None
    farm_id: str | None = None
    inputs: dict[str, ModelInputValue]
    parameters: dict[str, object] = Field(default_factory=dict)
