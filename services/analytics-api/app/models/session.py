from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.person import Person
    from app.models.zone_visit import ZoneVisit


class VisitSession(Base):
    __tablename__ = "sessions"

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[str] = mapped_column(String(16), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False)
    person_id: Mapped[str] = mapped_column(String(64), ForeignKey("persons.person_id", ondelete="CASCADE"), nullable=False)
    primary_track_id: Mapped[int | None] = mapped_column(Integer)
    visit_number: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_reason: Mapped[str | None] = mapped_column(String(32))
    person_type: Mapped[str] = mapped_column(String(16), default="customer")
    entry_counted: Mapped[bool] = mapped_column(Boolean, default=True)
    zones_visited: Mapped[list | None] = mapped_column(ARRAY(String))
    max_funnel_stage: Mapped[str | None] = mapped_column(String(32))
    dwell_total_sec: Mapped[int] = mapped_column(Integer, default=0)
    is_engaged: Mapped[bool] = mapped_column(Boolean, default=False)
    reached_checkout: Mapped[bool] = mapped_column(Boolean, default=False)
    checkout_dwell_sec: Mapped[int] = mapped_column(Integer, default=0)
    is_converted: Mapped[bool] = mapped_column(Boolean, default=False)
    pos_order_id: Mapped[str | None] = mapped_column(String(32))
    invoice_number: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    person: Mapped[Person] = relationship(back_populates="sessions")
    zone_visits: Mapped[list[ZoneVisit]] = relationship(back_populates="session", cascade="all, delete-orphan")
    events: Mapped[list[Event]] = relationship(back_populates="session")

    __table_args__ = (
        Index("ix_sessions_store_started", "store_id", "started_at"),
        Index("ix_sessions_person_started", "person_id", "started_at"),
        Index("ix_sessions_store_converted", "store_id", "is_converted", "started_at"),
        Index("ix_sessions_store_checkout", "store_id", "reached_checkout", "started_at"),
        Index("ix_sessions_track", "primary_track_id"),
    )
