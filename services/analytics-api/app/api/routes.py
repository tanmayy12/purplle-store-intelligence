from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.domain.metrics_service import MetricsService
from app.models import Anomaly, PosTransaction, TrackingEvent, VisitSession, Zone
from app.schemas import (
    AnomaliesListResponse,
    AnomalyResponse,
    AnomalySummaryResponse,
    EventsListResponse,
    EventResponse,
    FunnelResponse,
    MetricsResponse,
    PosListResponse,
    PosTransactionResponse,
    SessionResponse,
    SessionsListResponse,
    ZoneResponse,
)

router = APIRouter()


@router.get("/metrics", response_model=MetricsResponse)
def get_metrics(
    store_id: Optional[str] = None,
    date_str: Optional[str] = Query(None, alias="date"),
    db: Session = Depends(get_db),
) -> MetricsResponse:
    metric_date = date.fromisoformat(date_str) if date_str else None
    return MetricsService(db).get_metrics(store_id=store_id, metric_date=metric_date)


@router.get("/funnel", response_model=FunnelResponse)
def get_funnel(
    store_id: Optional[str] = None,
    date_str: Optional[str] = Query(None, alias="date"),
    db: Session = Depends(get_db),
) -> FunnelResponse:
    metric_date = date.fromisoformat(date_str) if date_str else None
    return MetricsService(db).get_funnel(store_id=store_id, metric_date=metric_date)


@router.get("/events", response_model=EventsListResponse)
def list_events(
    event_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> EventsListResponse:
    query = db.query(TrackingEvent).filter(TrackingEvent.store_id == settings.store_id)
    if event_type:
        query = query.filter(TrackingEvent.event_type == event_type)
    total = query.count()
    rows = query.order_by(TrackingEvent.timestamp.desc()).offset(offset).limit(limit).all()
    return EventsListResponse(
        total=total,
        items=[
            EventResponse(
                event_id=row.event_id,
                event_type=row.canonical_type or row.event_type,
                timestamp=row.timestamp,
                track_id=(
                    row.metadata_json.get("track_id")
                    if isinstance(row.metadata_json, dict)
                    else None
                ),
                session_id=row.session_id,
                zone_id=row.zone_id or (
                    row.metadata_json.get("zone_id") if isinstance(row.metadata_json, dict) else None
                ),
                payload=row.metadata_json or {},
            )
            for row in rows
        ],
    )


@router.get("/sessions", response_model=SessionsListResponse)
def list_sessions(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> SessionsListResponse:
    query = db.query(VisitSession).filter(VisitSession.store_id == settings.store_id)
    total = query.count()
    rows = query.order_by(VisitSession.started_at.desc()).offset(offset).limit(limit).all()
    return SessionsListResponse(
        total=total,
        items=[
            SessionResponse(
                session_id=row.session_id,
                started_at=row.started_at,
                ended_at=row.ended_at,
                person_type=row.person_type,
                zones_visited=row.zones_visited or [],
                dwell_total_sec=row.dwell_total_sec or 0,
                is_engaged=row.is_engaged,
                reached_checkout=row.reached_checkout,
                is_converted=row.is_converted,
                invoice_number=row.invoice_number,
            )
            for row in rows
        ],
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: UUID, db: Session = Depends(get_db)) -> SessionResponse:
    row = db.query(VisitSession).filter(VisitSession.session_id == session_id).first()
    if not row:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(
        session_id=row.session_id,
        started_at=row.started_at,
        ended_at=row.ended_at,
        person_type=row.person_type,
        zones_visited=row.zones_visited or [],
        dwell_total_sec=row.dwell_total_sec or 0,
        is_engaged=row.is_engaged,
        reached_checkout=row.reached_checkout,
        is_converted=row.is_converted,
        invoice_number=row.invoice_number,
    )


@router.get("/zones", response_model=list[ZoneResponse])
def list_zones(db: Session = Depends(get_db)) -> list[ZoneResponse]:
    zones = db.query(Zone).filter(Zone.store_id == settings.store_id).order_by(Zone.zone_name).all()
    return [
        ZoneResponse(
            zone_id=z.zone_id,
            zone_name=z.zone_name,
            zone_type=z.zone_type or "",
            department_map=z.department_map,
            is_staff_only=z.is_staff_only,
        )
        for z in zones
    ]


@router.get("/anomalies", response_model=AnomaliesListResponse)
def list_anomalies(
    severity: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> AnomaliesListResponse:
    query = db.query(Anomaly).filter(Anomaly.store_id == settings.store_id)
    if severity:
        query = query.filter(Anomaly.severity == severity)
    total = query.count()
    rows = query.order_by(Anomaly.detected_at.desc()).limit(limit).all()
    return AnomaliesListResponse(
        total=total,
        items=[
            AnomalyResponse(
                anomaly_id=row.anomaly_id,
                anomaly_type=row.anomaly_type,
                severity=row.severity or "low",
                detected_at=row.detected_at,
                track_id=(
                    row.evidence.get("track_id")
                    if isinstance(row.evidence, dict)
                    else None
                ),
                zone_id=row.zone_id,
                description=row.description or "",
                evidence=row.evidence,
            )
            for row in rows
        ],
    )


@router.get("/anomalies/summary", response_model=AnomalySummaryResponse)
def anomaly_summary(db: Session = Depends(get_db)) -> AnomalySummaryResponse:
    rows = db.query(Anomaly).filter(Anomaly.store_id == settings.store_id).all()
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for row in rows:
        by_type[row.anomaly_type] = by_type.get(row.anomaly_type, 0) + 1
        sev = row.severity or "low"
        by_severity[sev] = by_severity.get(sev, 0) + 1
    return AnomalySummaryResponse(total=len(rows), by_type=by_type, by_severity=by_severity)


@router.get("/pos/transactions", response_model=PosListResponse)
def list_pos_transactions(db: Session = Depends(get_db)) -> PosListResponse:
    rows = (
        db.query(PosTransaction)
        .filter(PosTransaction.store_id == settings.store_id)
        .order_by(PosTransaction.transaction_at)
        .all()
    )
    return PosListResponse(
        total=len(rows),
        items=[
            PosTransactionResponse(
                order_id=row.order_id,
                invoice_number=row.invoice_number,
                transaction_at=row.transaction_at,
                nmv=row.nmv or 0,
                item_count=row.item_count or 0,
                departments=row.departments or [],
                salesperson_name=row.salesperson_name,
                customer_name=row.customer_name,
            )
            for row in rows
        ],
    )
