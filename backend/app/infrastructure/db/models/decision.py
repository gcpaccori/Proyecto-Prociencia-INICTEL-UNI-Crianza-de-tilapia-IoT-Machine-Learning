from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.infrastructure.db.models.mixins import IdMixin


class AlertEvent(IdMixin, Base):
    __tablename__ = "alert_event"
    __table_args__ = {"schema": "decision"}

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    farm_id: Mapped[UUID] = mapped_column(
        ForeignKey("aquaculture.farm.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pond_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("aquaculture.pond.id", ondelete="SET NULL"),
    )
    alert_code: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source_model_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("models.model_run.id", ondelete="SET NULL"),
    )
    source_prediction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("timeseries.model_prediction.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Recommendation(IdMixin, Base):
    __tablename__ = "recommendation"
    __table_args__ = {"schema": "decision"}

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    farm_id: Mapped[UUID] = mapped_column(
        ForeignKey("aquaculture.farm.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pond_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("aquaculture.pond.id", ondelete="SET NULL"),
    )
    recommendation_code: Mapped[str] = mapped_column(String(128), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    model_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("models.model_run.id", ondelete="SET NULL"),
    )
    alert_event_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("decision.alert_event.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
