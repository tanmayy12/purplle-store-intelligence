import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    anomaly_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    store_id: Mapped[str] = mapped_column(String(16), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False)
    person_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("persons.person_id", ondelete="SET NULL"))
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.session_id", ondelete="SET NULL")
    )
    zone_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("zones.zone_id", ondelete="SET NULL"))
    anomaly_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="low")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict | None] = mapped_column(JSONB)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_anomalies_store_detected", "store_id", "detected_at"),
        Index("ix_anomalies_store_type", "store_id", "anomaly_type", "detected_at"),
        Index("ix_anomalies_unresolved", "store_id", "severity"),
        Index("ix_anomalies_session", "session_id"),
        Index("ix_anomalies_person", "person_id"),
    )
