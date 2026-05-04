from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.infrastructure.db.models.mixins import IdMixin, TimestampMixin


class ModelDefinition(IdMixin, TimestampMixin, Base):
    __tablename__ = "model_definition"
    __table_args__ = {"schema": "models"}

    model_code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_report: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    implementation_status: Mapped[str] = mapped_column(String(64), nullable=False)
    assumptions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class ModelVersion(IdMixin, Base):
    __tablename__ = "model_version"
    __table_args__ = {"schema": "models"}

    model_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.model_definition.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(255))
    artifact_uri: Mapped[str | None] = mapped_column(String(1024))
    parameters_schema: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModelSourceReference(IdMixin, Base):
    __tablename__ = "model_source_reference"
    __table_args__ = {"schema": "models"}

    model_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.model_definition.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_report: Mapped[str] = mapped_column(String(64), nullable=False)
    markdown_file: Mapped[str] = mapped_column(String(512), nullable=False)
    reference_detail: Mapped[str | None] = mapped_column(String(512))
    equation_status: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModelParameter(IdMixin, Base):
    __tablename__ = "model_parameter"
    __table_args__ = {"schema": "models"}

    model_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.model_version.id", ondelete="CASCADE"),
        nullable=False,
    )
    parameter_name: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModelParameterSet(IdMixin, Base):
    __tablename__ = "model_parameter_set"
    __table_args__ = {"schema": "models"}

    model_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.model_version.id", ondelete="CASCADE"),
        nullable=False,
    )
    parameter_set_code: Mapped[str] = mapped_column(String(128), nullable=False)
    parameters: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModelInputSchema(IdMixin, Base):
    __tablename__ = "model_input_schema"
    __table_args__ = {"schema": "models"}

    model_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.model_version.id", ondelete="CASCADE"),
        nullable=False,
    )
    schema_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    unit_map: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModelOutputSchema(IdMixin, Base):
    __tablename__ = "model_output_schema"
    __table_args__ = {"schema": "models"}

    model_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.model_version.id", ondelete="CASCADE"),
        nullable=False,
    )
    schema_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    unit_map: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModelRun(IdMixin, Base):
    __tablename__ = "model_run"
    __table_args__ = {"schema": "models"}

    run_code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    model_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.model_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    parameter_set_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("models.model_parameter_set.id", ondelete="SET NULL"),
    )
    model_code: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_report: Mapped[str] = mapped_column(String(64), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(255))
    input_data: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    parameters: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    output_data: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    execution_status: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModelRunInput(IdMixin, Base):
    __tablename__ = "model_run_input"
    __table_args__ = {"schema": "models"}

    model_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.model_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    input_name: Mapped[str] = mapped_column(String(128), nullable=False)
    input_value: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32))
    source_measurement_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("iot.sensor_measurement_clean.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModelRunOutput(IdMixin, Base):
    __tablename__ = "model_run_output"
    __table_args__ = {"schema": "models"}

    model_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.model_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    output_name: Mapped[str] = mapped_column(String(128), nullable=False)
    output_value: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
