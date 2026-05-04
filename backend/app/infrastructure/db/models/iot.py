from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.infrastructure.db.models.mixins import IdMixin, TimestampMixin


class Sensor(IdMixin, TimestampMixin, Base):
    __tablename__ = "sensor"
    __table_args__ = {"schema": "iot"}

    farm_id: Mapped[UUID] = mapped_column(
        ForeignKey("aquaculture.farm.id", ondelete="CASCADE"),
        nullable=False,
    )
    pond_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("aquaculture.pond.id", ondelete="SET NULL"),
    )
    channel_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("aquaculture.channel.id", ondelete="SET NULL"),
    )
    sensor_code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    variable_code: Mapped[str] = mapped_column(String(64), nullable=False)
    sensor_type: Mapped[str | None] = mapped_column(String(128))
    manufacturer: Mapped[str | None] = mapped_column(String(255))
    model_name: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(String(255))
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    extra_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )


class SensorCalibration(IdMixin, Base):
    __tablename__ = "sensor_calibration"
    __table_args__ = {"schema": "iot"}

    sensor_id: Mapped[UUID] = mapped_column(
        ForeignKey("iot.sensor.id", ondelete="CASCADE"),
        nullable=False,
    )
    calibrated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    variable_code: Mapped[str] = mapped_column(String(64), nullable=False)
    method: Mapped[str | None] = mapped_column(String(128))
    coefficients: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    performed_by: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SensorMeasurementRaw(IdMixin, Base):
    __tablename__ = "sensor_measurement_raw"
    __table_args__ = {"schema": "iot"}

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    farm_id: Mapped[UUID] = mapped_column(
        ForeignKey("aquaculture.farm.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pond_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("aquaculture.pond.id", ondelete="SET NULL"),
    )
    sensor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("iot.sensor.id", ondelete="SET NULL"),
    )
    variable_code: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    raw_unit: Mapped[str | None] = mapped_column(String(32))
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SensorMeasurementClean(IdMixin, Base):
    __tablename__ = "sensor_measurement_clean"
    __table_args__ = {"schema": "iot"}

    raw_measurement_id: Mapped[UUID] = mapped_column(
        ForeignKey("iot.sensor_measurement_raw.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    farm_id: Mapped[UUID] = mapped_column(
        ForeignKey("aquaculture.farm.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pond_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("aquaculture.pond.id", ondelete="SET NULL"),
    )
    sensor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("iot.sensor.id", ondelete="SET NULL"),
    )
    variable_code: Mapped[str] = mapped_column(String(64), nullable=False)
    clean_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    standard_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_flag: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(64), nullable=False)
    cleaning_method: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
