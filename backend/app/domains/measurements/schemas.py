from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RawMeasurementCreate(BaseModel):
    time: datetime = Field(default_factory=utc_now)
    farm_id: str = Field(min_length=1)
    pond_id: str | None = None
    sensor_id: str | None = None
    variable_code: str = Field(min_length=1)
    raw_value: float | None = None
    raw_unit: str | None = None
    raw_payload: dict[str, object] = Field(default_factory=dict)
    source_type: str = "manual"


class RawMeasurementRead(RawMeasurementCreate):
    id: str
    created_at: datetime = Field(default_factory=utc_now)


class CleanMeasurementRead(BaseModel):
    id: str
    raw_measurement_id: str
    time: datetime
    farm_id: str
    pond_id: str | None = None
    sensor_id: str | None = None
    variable_code: str
    clean_value: float
    standard_unit: str
    quality_flag: str
    validation_status: str
    cleaning_method: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class MeasurementIngestionResult(BaseModel):
    raw_measurement: RawMeasurementRead
    clean_measurement: CleanMeasurementRead | None = None
    warnings: list[str] = Field(default_factory=list)
