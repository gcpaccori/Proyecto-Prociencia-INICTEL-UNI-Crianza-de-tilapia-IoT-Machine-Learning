from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.infrastructure.db.models.mixins import IdMixin, TimestampMixin


class Actuator(IdMixin, TimestampMixin, Base):
    __tablename__ = "actuator"
    __table_args__ = {"schema": "actuation"}

    farm_id: Mapped[UUID] = mapped_column(
        ForeignKey("aquaculture.farm.id", ondelete="CASCADE"),
        nullable=False,
    )
    pond_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("aquaculture.pond.id", ondelete="SET NULL"),
    )
    actuator_code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    actuator_type: Mapped[str] = mapped_column(String(64), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extra_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )


class Command(IdMixin, Base):
    __tablename__ = "command"
    __table_args__ = {"schema": "actuation"}

    actuator_id: Mapped[UUID] = mapped_column(
        ForeignKey("actuation.actuator.id", ondelete="RESTRICT"),
        nullable=False,
    )
    recommendation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("decision.recommendation.id", ondelete="SET NULL"),
    )
    command_type: Mapped[str] = mapped_column(String(64), nullable=False)
    command_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(128))
    execution_status: Mapped[str] = mapped_column(String(64), nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
