from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FarmCreate(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    extra_metadata: dict[str, object] = Field(default_factory=dict)


class FarmRead(FarmCreate):
    id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PondCreate(BaseModel):
    farm_id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    pond_type: str | None = None
    water_volume_l: float | None = None
    surface_area_m2: float | None = None
    extra_metadata: dict[str, object] = Field(default_factory=dict)


class PondRead(PondCreate):
    id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SensorCreate(BaseModel):
    farm_id: str = Field(min_length=1)
    pond_id: str | None = None
    sensor_code: str = Field(min_length=1)
    variable_code: str = Field(min_length=1)
    sensor_type: str | None = None
    manufacturer: str | None = None
    model_name: str | None = None
    serial_number: str | None = None
    status: str = "active"
    extra_metadata: dict[str, object] = Field(default_factory=dict)


class SensorRead(SensorCreate):
    id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
