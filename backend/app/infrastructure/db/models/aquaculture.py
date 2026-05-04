from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.infrastructure.db.models.mixins import IdMixin, TimestampMixin


class Farm(IdMixin, TimestampMixin, Base):
    __tablename__ = "farm"
    __table_args__ = {"schema": "aquaculture"}

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location_name: Mapped[str | None] = mapped_column(String(255))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    extra_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )


class Pond(IdMixin, TimestampMixin, Base):
    __tablename__ = "pond"
    __table_args__ = {"schema": "aquaculture"}

    farm_id: Mapped[UUID] = mapped_column(
        ForeignKey("aquaculture.farm.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    pond_type: Mapped[str | None] = mapped_column(String(64))
    water_volume_l: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    surface_area_m2: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    extra_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )


class Channel(IdMixin, TimestampMixin, Base):
    __tablename__ = "channel"
    __table_args__ = {"schema": "aquaculture"}

    farm_id: Mapped[UUID] = mapped_column(
        ForeignKey("aquaculture.farm.id", ondelete="CASCADE"),
        nullable=False,
    )
    pond_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("aquaculture.pond.id", ondelete="SET NULL"),
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    flow_rate_l_h: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    volume_l: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    extra_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )


class Species(IdMixin, TimestampMixin, Base):
    __tablename__ = "species"
    __table_args__ = {"schema": "aquaculture"}

    scientific_name: Mapped[str] = mapped_column(String(255), nullable=False)
    common_name: Mapped[str | None] = mapped_column(String(255))
    source_reference: Mapped[str | None] = mapped_column(String(255))


class FishBatch(IdMixin, TimestampMixin, Base):
    __tablename__ = "fish_batch"
    __table_args__ = {"schema": "aquaculture"}

    pond_id: Mapped[UUID] = mapped_column(
        ForeignKey("aquaculture.pond.id", ondelete="RESTRICT"),
        nullable=False,
    )
    species_id: Mapped[UUID] = mapped_column(
        ForeignKey("aquaculture.species.id", ondelete="RESTRICT"),
        nullable=False,
    )
    batch_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    stocking_date: Mapped[date | None] = mapped_column(Date)
    initial_count: Mapped[int | None] = mapped_column(Integer)
    initial_average_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    current_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class BiomassSampling(IdMixin, Base):
    __tablename__ = "biomass_sampling"
    __table_args__ = {"schema": "aquaculture"}

    fish_batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("aquaculture.fish_batch.id", ondelete="CASCADE"),
        nullable=False,
    )
    pond_id: Mapped[UUID] = mapped_column(
        ForeignKey("aquaculture.pond.id", ondelete="RESTRICT"),
        nullable=False,
    )
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sample_count: Mapped[int | None] = mapped_column(Integer)
    average_weight_g: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    biomass_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    method: Mapped[str | None] = mapped_column(String(128))
    unit_map: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MortalityEvent(IdMixin, Base):
    __tablename__ = "mortality_event"
    __table_args__ = {"schema": "aquaculture"}

    fish_batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("aquaculture.fish_batch.id", ondelete="CASCADE"),
        nullable=False,
    )
    pond_id: Mapped[UUID] = mapped_column(
        ForeignKey("aquaculture.pond.id", ondelete="RESTRICT"),
        nullable=False,
    )
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mortality_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cause: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FeedProduct(IdMixin, TimestampMixin, Base):
    __tablename__ = "feed_product"
    __table_args__ = {"schema": "aquaculture"}

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(255))
    pellet_size_mm: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    extra_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )


class FeedComposition(IdMixin, Base):
    __tablename__ = "feed_composition"
    __table_args__ = {"schema": "aquaculture"}

    feed_product_id: Mapped[UUID] = mapped_column(
        ForeignKey("aquaculture.feed_product.id", ondelete="CASCADE"),
        nullable=False,
    )
    protein_pct: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    lipid_pct: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    carbohydrate_pct: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    energy_kj_g: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    digestibility_protein: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    digestibility_lipid: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    digestibility_carb: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    effective_from: Mapped[date | None] = mapped_column(Date)
    source_reference: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FeedingEvent(IdMixin, Base):
    __tablename__ = "feeding_event"
    __table_args__ = {"schema": "aquaculture"}

    pond_id: Mapped[UUID] = mapped_column(
        ForeignKey("aquaculture.pond.id", ondelete="RESTRICT"),
        nullable=False,
    )
    fish_batch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("aquaculture.fish_batch.id", ondelete="SET NULL"),
    )
    feed_product_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("aquaculture.feed_product.id", ondelete="SET NULL"),
    )
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    feed_amount_g: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    feed_unit: Mapped[str] = mapped_column(String(16), default="g", nullable=False)
    feeding_method: Mapped[str | None] = mapped_column(String(128))
    operator: Mapped[str | None] = mapped_column(String(128))
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
