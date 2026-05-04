from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ActuatorStatus(BaseModel):
    actuator_id: str
    actuator_type: str
    status: str
    pond_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class ActuatorCreate(BaseModel):
    farm_id: str
    pond_id: str | None = None
    actuator_code: str
    actuator_type: str
    manufacturer: str | None = None
    status: str = "active"
    extra_metadata: dict[str, object] = Field(default_factory=dict)


class ActuatorRead(ActuatorCreate):
    id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SafetyPolicy(BaseModel):
    allow_automatic_commands: bool = False
    allowed_actuator_types: list[str] = Field(default_factory=list)
    manual_approval_required: bool = True
    max_commands_per_recommendation: int = Field(default=1, ge=1)


class UserApproval(BaseModel):
    approved: bool
    approved_by: str | None = None
    approval_note: str | None = None
    approved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ActuationCommandDraft(BaseModel):
    command_id: str | None = None
    actuator_id: str
    command_type: str
    command_payload: dict[str, object]
    execution_status: str = "pending_dispatch"
    requested_by: str | None = None
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    audit_record: dict[str, object] = Field(default_factory=dict)


class ActuationDecision(BaseModel):
    command_status: str
    command: ActuationCommandDraft | None = None
    audit_record: dict[str, object] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ActuationCommandRequest(BaseModel):
    recommendation_code: str
    safety_policy: SafetyPolicy = Field(default_factory=SafetyPolicy)
    user_approval: UserApproval | None = None
