from datetime import datetime

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.infrastructure.db.models.mixins import IdMixin


class AuditLog(IdMixin, Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "audit"}

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_schema: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_table: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64))
    source_data_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_data_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
