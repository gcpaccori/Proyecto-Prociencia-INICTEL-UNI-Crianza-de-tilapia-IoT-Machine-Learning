from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.infrastructure.db.models.mixins import IdMixin


class ModelPrediction(IdMixin, Base):
    __tablename__ = "model_prediction"
    __table_args__ = {"schema": "timeseries"}

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.model_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    model_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.model_run.id", ondelete="RESTRICT"),
        nullable=False,
    )
    input_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    predicted_variable: Mapped[str] = mapped_column(String(128), nullable=False)
    predicted_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
