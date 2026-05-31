from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.session import VisitSession


class ZoneVisit(Base):
    __tablename__ = "zone_visits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    person_id: Mapped[str] = mapped_column(String(64), ForeignKey("persons.person_id", ondelete="CASCADE"), nullable=False)
    zone_id: Mapped[str] = mapped_column(String(64), ForeignKey("zones.zone_id", ondelete="CASCADE"), nullable=False)
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dwell_sec: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped[VisitSession] = relationship(back_populates="zone_visits")

    __table_args__ = (
        UniqueConstraint("session_id", "zone_id", "entered_at", name="uq_zone_visits_session_zone_entered"),
        Index("ix_zone_visits_session", "session_id"),
        Index("ix_zone_visits_zone_entered", "zone_id", "entered_at"),
        Index("ix_zone_visits_person_entered", "person_id", "entered_at"),
        Index("ix_zone_visits_store_lookup", "zone_id", "session_id"),
    )
