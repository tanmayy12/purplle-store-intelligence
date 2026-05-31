from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StoreMetric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String(16), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    metric_hour: Mapped[int | None] = mapped_column(SmallInteger)
    granularity: Mapped[str] = mapped_column(String(16), nullable=False, default="daily")
    total_entries: Mapped[int] = mapped_column(Integer, default=0)
    unique_sessions: Mapped[int] = mapped_column(Integer, default=0)
    staff_excluded: Mapped[int] = mapped_column(Integer, default=0)
    engaged_visits: Mapped[int] = mapped_column(Integer, default=0)
    checkout_visits: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    conversion_rate: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    total_nmv: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    avg_dwell_sec: Mapped[int] = mapped_column(Integer, default=0)
    avg_basket_nmv: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    pos_transactions: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("store_id", "metric_date", "granularity", "metric_hour", name="uq_metrics_store_period"),
        Index("ix_metrics_store_date", "store_id", "metric_date"),
        Index("ix_metrics_store_granularity", "store_id", "granularity", "metric_date"),
    )
