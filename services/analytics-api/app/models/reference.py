from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Store(Base):
    __tablename__ = "stores"

    store_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    store_name: Mapped[str] = mapped_column(String(128), nullable=False)
    city: Mapped[str | None] = mapped_column(String(64))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    operating_date: Mapped[Date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Zone(Base):
    __tablename__ = "zones"

    zone_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    store_id: Mapped[str] = mapped_column(String(16), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False)
    zone_name: Mapped[str] = mapped_column(String(128), nullable=False)
    zone_type: Mapped[str | None] = mapped_column(String(32))
    department_map: Mapped[str | None] = mapped_column(String(64))
    polygon_json: Mapped[dict | None] = mapped_column(JSONB)
    is_staff_only: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (Index("ix_zones_store_id", "store_id"),)


class PosTransaction(Base):
    __tablename__ = "pos_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(32), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    store_id: Mapped[str] = mapped_column(String(16), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False)
    transaction_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    nmv: Mapped[float] = mapped_column(default=0.0)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    departments: Mapped[list | None] = mapped_column(JSONB)
    salesperson_id: Mapped[str | None] = mapped_column(String(16))
    salesperson_name: Mapped[str | None] = mapped_column(String(128))
    customer_name: Mapped[str | None] = mapped_column(String(128))
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("ix_pos_transactions_store_txn_at", "store_id", "transaction_at"),
        Index("ix_pos_transactions_invoice", "invoice_number"),
    )


class PosLineItem(Base):
    __tablename__ = "pos_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(32), nullable=False)
    invoice_number: Mapped[str] = mapped_column(
        String(64), ForeignKey("pos_transactions.invoice_number", ondelete="CASCADE"), nullable=False
    )
    sku: Mapped[str | None] = mapped_column(String(64))
    product_name: Mapped[str | None] = mapped_column(Text)
    brand_name: Mapped[str | None] = mapped_column(String(128))
    dep_name: Mapped[str | None] = mapped_column(String(64))
    sub_category: Mapped[str | None] = mapped_column(String(128))
    qty: Mapped[int] = mapped_column(Integer, default=1)
    nmv: Mapped[float] = mapped_column(default=0.0)

    __table_args__ = (Index("ix_pos_line_items_invoice", "invoice_number"),)
