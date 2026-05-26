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


class ModelInputFieldAudit(BaseModel):
    input_name: str
    unit: str
    status: str
    control: str
    source: str | None = None
    value_preview: object | None = None
    options: list[str] = Field(default_factory=list)
    note: str | None = None


class ModelInputAudit(BaseModel):
    model_code: str
    readiness_status: str
    pond_id: str | None = None
    can_run_now: bool
    can_run_dry_run: bool
    auto_inputs: dict[str, ModelInputValue] = Field(default_factory=dict)
    form_fields: list[ModelInputFieldAudit] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    frontend_status: str


class ModelRunRequest(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pond_id: str | None = None
    farm_id: str | None = None
    inputs: dict[str, ModelInputValue]
    parameters: dict[str, object] = Field(default_factory=dict)


class ModelTestPayload(BaseModel):
    model_code: str
    pond_id: str | None = None
    readiness_status: str
    request: ModelRunRequest
    auto_input_names: list[str] = Field(default_factory=list)
    generated_input_names: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    test_mode: str
    notes: list[str] = Field(default_factory=list)


class ModelTestRunItem(BaseModel):
    model_code: str
    status: str
    readiness_status: str
    run_id: str | None = None
    auto_input_names: list[str] = Field(default_factory=list)
    generated_input_names: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class ModelBatchTestRun(BaseModel):
    pond_id: str | None = None
    total: int
    succeeded: int
    failed: int
    results: list[ModelTestRunItem]
