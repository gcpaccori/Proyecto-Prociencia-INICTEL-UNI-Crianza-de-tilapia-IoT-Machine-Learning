from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


class ModelRunContext(BaseModel):
    model_code: str
    model_version: str
    source_report: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pond_id: str | None = None
    farm_id: str | None = None
    model_version_id: UUID | None = None
    parameter_set_id: UUID | None = None
    source_reference: str | None = None
    input_window_start: datetime | None = None
    input_window_end: datetime | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
