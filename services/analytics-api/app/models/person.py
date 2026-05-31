from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.session import VisitSession


class Person(Base):
    __tablename__ = "persons"

    person_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    store_id: Mapped[str] = mapped_column(String(16), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False)
    person_type: Mapped[str] = mapped_column(String(16), default="customer")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    visit_count: Mapped[int] = mapped_column(Integer, default=0)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    last_track_id: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    sessions: Mapped[list[VisitSession]] = relationship(back_populates="person")
    events: Mapped[list[Event]] = relationship(back_populates="person")

    __table_args__ = (
        Index("ix_persons_store_type", "store_id", "person_type"),
        Index("ix_persons_store_last_seen", "store_id", "last_seen_at"),
        Index("ix_persons_store_staff", "store_id", "is_staff"),
    )
