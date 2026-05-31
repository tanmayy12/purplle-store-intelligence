from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    database: str
    kafka: str
    consumer_running: bool


class FootfallMetrics(BaseModel):
    total_entries: int
    unique_sessions: int
    staff_excluded: int
    re_entries: int = 0


class EngagementMetrics(BaseModel):
    engaged_visits: int
    engagement_rate: float
    avg_dwell_sec: int
    avg_zones_per_visit: float


class ConversionMetrics(BaseModel):
    checkout_proximity_visits: int
    pos_transactions: int
    matched_conversions: int
    conversion_rate: float
    conversion_rate_vs_pos: float
    unmatched_pos: int


class RevenueMetrics(BaseModel):
    total_nmv: float
    total_gmv: float = 0
    avg_basket_nmv: float
    avg_items_per_transaction: float
    discount_rate: float = 0
    revenue_per_visitor: float


class HourlyMetric(BaseModel):
    hour: str
    entries: int
    transactions: int
    nmv: float
    conversion_rate: float


class ZoneStat(BaseModel):
    zone_id: str
    zone_name: str
    visits: int
    avg_dwell_sec: int


class DepartmentMix(BaseModel):
    department: str
    nmv: float
    qty: int
    share: float


class MetricsResponse(BaseModel):
    store_id: str
    store_name: str
    date: str
    footfall: FootfallMetrics
    engagement: EngagementMetrics
    conversion: ConversionMetrics
    revenue: RevenueMetrics
    hourly: list[HourlyMetric]
    top_zones: list[ZoneStat]
    department_mix: list[DepartmentMix]
    computed_at: datetime


class FunnelStage(BaseModel):
    stage: str
    stage_order: int
    count: int
    pct_of_top: float
    drop_off_from_prev: float | None = None
    definition: str | None = None


class FunnelResponse(BaseModel):
    store_id: str
    date: str
    funnel_type: str = "session_based"
    stages: list[FunnelStage]
    notes: str


class EventResponse(BaseModel):
    event_id: UUID
    event_type: str
    timestamp: datetime
    track_id: int | None
    session_id: UUID | None
    zone_id: str | None
    payload: dict[str, Any]


class EventsListResponse(BaseModel):
    total: int
    items: list[EventResponse]


class SessionResponse(BaseModel):
    session_id: UUID
    started_at: datetime
    ended_at: datetime | None
    person_type: str
    zones_visited: list[str]
    dwell_total_sec: int
    is_engaged: bool
    reached_checkout: bool
    is_converted: bool
    invoice_number: str | None


class SessionsListResponse(BaseModel):
    total: int
    items: list[SessionResponse]


class ZoneResponse(BaseModel):
    zone_id: str
    zone_name: str
    zone_type: str
    department_map: str | None
    is_staff_only: bool
    visits: int = 0
    avg_dwell_sec: int = 0


class AnomalyResponse(BaseModel):
    anomaly_id: UUID
    anomaly_type: str
    severity: str
    detected_at: datetime
    track_id: int | None
    zone_id: str | None
    description: str
    evidence: dict[str, Any] | None = None


class AnomaliesListResponse(BaseModel):
    total: int
    items: list[AnomalyResponse]


class AnomalySummaryResponse(BaseModel):
    total: int
    by_type: dict[str, int]
    by_severity: dict[str, int]


class PosTransactionResponse(BaseModel):
    order_id: str
    invoice_number: str
    transaction_at: datetime
    nmv: float
    item_count: int
    departments: list[str]
    salesperson_name: str | None
    customer_name: str | None


class PosListResponse(BaseModel):
    total: int
    items: list[PosTransactionResponse]
