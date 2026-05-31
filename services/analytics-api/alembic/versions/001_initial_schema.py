"""Initial PostgreSQL schema for store intelligence analytics.

Revision ID: 001
Revises:
Create Date: 2026-05-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stores",
        sa.Column("store_id", sa.String(length=16), nullable=False),
        sa.Column("store_name", sa.String(length=128), nullable=False),
        sa.Column("city", sa.String(length=64), nullable=True),
        sa.Column("timezone", sa.String(length=64), server_default="Asia/Kolkata", nullable=False),
        sa.Column("operating_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("store_id"),
    )

    op.create_table(
        "zones",
        sa.Column("zone_id", sa.String(length=64), nullable=False),
        sa.Column("store_id", sa.String(length=16), nullable=False),
        sa.Column("zone_name", sa.String(length=128), nullable=False),
        sa.Column("zone_type", sa.String(length=32), nullable=True),
        sa.Column("department_map", sa.String(length=64), nullable=True),
        sa.Column("polygon_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_staff_only", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("zone_id"),
    )
    op.create_index("ix_zones_store_id", "zones", ["store_id"], unique=False)

    op.create_table(
        "persons",
        sa.Column("person_id", sa.String(length=64), nullable=False),
        sa.Column("store_id", sa.String(length=16), nullable=False),
        sa.Column("person_type", sa.String(length=16), server_default="customer", nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("visit_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_staff", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_track_id", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("person_id"),
    )
    op.create_index("ix_persons_store_type", "persons", ["store_id", "person_type"], unique=False)
    op.create_index("ix_persons_store_last_seen", "persons", ["store_id", "last_seen_at"], unique=False)
    op.create_index("ix_persons_store_staff", "persons", ["store_id", "is_staff"], unique=False)

    op.create_table(
        "sessions",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", sa.String(length=16), nullable=False),
        sa.Column("person_id", sa.String(length=64), nullable=False),
        sa.Column("primary_track_id", sa.Integer(), nullable=True),
        sa.Column("visit_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_reason", sa.String(length=32), nullable=True),
        sa.Column("person_type", sa.String(length=16), server_default="customer", nullable=False),
        sa.Column("entry_counted", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("zones_visited", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("max_funnel_stage", sa.String(length=32), nullable=True),
        sa.Column("dwell_total_sec", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_engaged", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("reached_checkout", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("checkout_dwell_sec", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_converted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("pos_order_id", sa.String(length=32), nullable=True),
        sa.Column("invoice_number", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["persons.person_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_sessions_store_started", "sessions", ["store_id", "started_at"], unique=False)
    op.create_index("ix_sessions_person_started", "sessions", ["person_id", "started_at"], unique=False)
    op.create_index(
        "ix_sessions_store_converted", "sessions", ["store_id", "is_converted", "started_at"], unique=False
    )
    op.create_index(
        "ix_sessions_store_checkout", "sessions", ["store_id", "reached_checkout", "started_at"], unique=False
    )
    op.create_index("ix_sessions_track", "sessions", ["primary_track_id"], unique=False)

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", sa.String(length=16), nullable=False),
        sa.Column("person_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("canonical_type", sa.String(length=64), nullable=True),
        sa.Column("zone_id", sa.String(length=64), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frame_index", sa.Integer(), nullable=True),
        sa.Column("video_time_sec", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["persons.person_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.zone_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_events_store_timestamp", "events", ["store_id", "timestamp"], unique=False)
    op.create_index("ix_events_person_timestamp", "events", ["person_id", "timestamp"], unique=False)
    op.create_index("ix_events_session_id", "events", ["session_id"], unique=False)
    op.create_index("ix_events_store_type_timestamp", "events", ["store_id", "event_type", "timestamp"], unique=False)
    op.create_index("ix_events_zone_timestamp", "events", ["zone_id", "timestamp"], unique=False)
    op.create_index("ix_events_event_id", "events", ["event_id"], unique=False)

    op.create_table(
        "zone_visits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", sa.String(length=64), nullable=False),
        sa.Column("zone_id", sa.String(length=64), nullable=False),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dwell_sec", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["persons.person_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.zone_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "zone_id", "entered_at", name="uq_zone_visits_session_zone_entered"),
    )
    op.create_index("ix_zone_visits_session", "zone_visits", ["session_id"], unique=False)
    op.create_index("ix_zone_visits_zone_entered", "zone_visits", ["zone_id", "entered_at"], unique=False)
    op.create_index("ix_zone_visits_person_entered", "zone_visits", ["person_id", "entered_at"], unique=False)
    op.create_index("ix_zone_visits_store_lookup", "zone_visits", ["zone_id", "session_id"], unique=False)

    op.create_table(
        "metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("store_id", sa.String(length=16), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("metric_hour", sa.SmallInteger(), nullable=True),
        sa.Column("granularity", sa.String(length=16), server_default="daily", nullable=False),
        sa.Column("total_entries", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unique_sessions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("staff_excluded", sa.Integer(), server_default="0", nullable=False),
        sa.Column("engaged_visits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("checkout_visits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("conversions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("conversion_rate", sa.Numeric(precision=8, scale=4), server_default="0", nullable=False),
        sa.Column("total_nmv", sa.Numeric(precision=14, scale=2), server_default="0", nullable=False),
        sa.Column("avg_dwell_sec", sa.Integer(), server_default="0", nullable=False),
        sa.Column("avg_basket_nmv", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False),
        sa.Column("pos_transactions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "store_id", "metric_date", "granularity", "metric_hour", name="uq_metrics_store_period"
        ),
    )
    op.create_index("ix_metrics_store_date", "metrics", ["store_id", "metric_date"], unique=False)
    op.create_index("ix_metrics_store_granularity", "metrics", ["store_id", "granularity", "metric_date"], unique=False)

    op.create_table(
        "anomalies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("anomaly_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", sa.String(length=16), nullable=False),
        sa.Column("person_id", sa.String(length=64), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("zone_id", sa.String(length=64), nullable=True),
        sa.Column("anomaly_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), server_default="low", nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["persons.person_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.zone_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("anomaly_id"),
    )
    op.create_index("ix_anomalies_store_detected", "anomalies", ["store_id", "detected_at"], unique=False)
    op.create_index("ix_anomalies_store_type", "anomalies", ["store_id", "anomaly_type", "detected_at"], unique=False)
    op.create_index("ix_anomalies_unresolved", "anomalies", ["store_id", "severity"], unique=False)
    op.create_index("ix_anomalies_session", "anomalies", ["session_id"], unique=False)
    op.create_index("ix_anomalies_person", "anomalies", ["person_id"], unique=False)

    op.create_table(
        "pos_transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.String(length=32), nullable=False),
        sa.Column("invoice_number", sa.String(length=64), nullable=False),
        sa.Column("store_id", sa.String(length=16), nullable=False),
        sa.Column("transaction_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("nmv", sa.Float(), server_default="0", nullable=False),
        sa.Column("item_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("departments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("salesperson_id", sa.String(length=16), nullable=True),
        sa.Column("salesperson_name", sa.String(length=128), nullable=True),
        sa.Column("customer_name", sa.String(length=128), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_number"),
    )
    op.create_index(
        "ix_pos_transactions_store_txn_at", "pos_transactions", ["store_id", "transaction_at"], unique=False
    )
    op.create_index("ix_pos_transactions_invoice", "pos_transactions", ["invoice_number"], unique=False)

    op.create_table(
        "pos_line_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.String(length=32), nullable=False),
        sa.Column("invoice_number", sa.String(length=64), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("brand_name", sa.String(length=128), nullable=True),
        sa.Column("dep_name", sa.String(length=64), nullable=True),
        sa.Column("sub_category", sa.String(length=128), nullable=True),
        sa.Column("qty", sa.Integer(), server_default="1", nullable=False),
        sa.Column("nmv", sa.Float(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["invoice_number"], ["pos_transactions.invoice_number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pos_line_items_invoice", "pos_line_items", ["invoice_number"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pos_line_items_invoice", table_name="pos_line_items")
    op.drop_table("pos_line_items")
    op.drop_index("ix_pos_transactions_invoice", table_name="pos_transactions")
    op.drop_index("ix_pos_transactions_store_txn_at", table_name="pos_transactions")
    op.drop_table("pos_transactions")
    op.drop_index("ix_anomalies_person", table_name="anomalies")
    op.drop_index("ix_anomalies_session", table_name="anomalies")
    op.drop_index("ix_anomalies_unresolved", table_name="anomalies")
    op.drop_index("ix_anomalies_store_type", table_name="anomalies")
    op.drop_index("ix_anomalies_store_detected", table_name="anomalies")
    op.drop_table("anomalies")
    op.drop_index("ix_metrics_store_granularity", table_name="metrics")
    op.drop_index("ix_metrics_store_date", table_name="metrics")
    op.drop_table("metrics")
    op.drop_index("ix_zone_visits_store_lookup", table_name="zone_visits")
    op.drop_index("ix_zone_visits_person_entered", table_name="zone_visits")
    op.drop_index("ix_zone_visits_zone_entered", table_name="zone_visits")
    op.drop_index("ix_zone_visits_session", table_name="zone_visits")
    op.drop_table("zone_visits")
    op.drop_index("ix_events_event_id", table_name="events")
    op.drop_index("ix_events_zone_timestamp", table_name="events")
    op.drop_index("ix_events_store_type_timestamp", table_name="events")
    op.drop_index("ix_events_session_id", table_name="events")
    op.drop_index("ix_events_person_timestamp", table_name="events")
    op.drop_index("ix_events_store_timestamp", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_sessions_track", table_name="sessions")
    op.drop_index("ix_sessions_store_checkout", table_name="sessions")
    op.drop_index("ix_sessions_store_converted", table_name="sessions")
    op.drop_index("ix_sessions_person_started", table_name="sessions")
    op.drop_index("ix_sessions_store_started", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_persons_store_staff", table_name="persons")
    op.drop_index("ix_persons_store_last_seen", table_name="persons")
    op.drop_index("ix_persons_store_type", table_name="persons")
    op.drop_table("persons")
    op.drop_index("ix_zones_store_id", table_name="zones")
    op.drop_table("zones")
    op.drop_table("stores")
