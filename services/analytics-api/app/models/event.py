from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.session import VisitSession


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    store_id: Mapped[str] = mapped_column(String(16), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False)
    person_id: Mapped[str] = mapped_column(String(64), ForeignKey("persons.person_id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.session_id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_type: Mapped[str | None] = mapped_column(String(64))
    zone_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("zones.zone_id", ondelete="SET NULL"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    frame_index: Mapped[int | None] = mapped_column(Integer)
    video_time_sec: Mapped[float | None] = mapped_column(Numeric(12, 3))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    person: Mapped[Person] = relationship(back_populates="events")
    session: Mapped[VisitSession | None] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_events_store_timestamp", "store_id", "timestamp"),
        Index("ix_events_person_timestamp", "person_id", "timestamp"),
        Index("ix_events_session_id", "session_id"),
        Index("ix_events_store_type_timestamp", "store_id", "event_type", "timestamp"),
        Index("ix_events_zone_timestamp", "zone_id", "timestamp"),
        Index("ix_events_event_id", "event_id"),
    )
