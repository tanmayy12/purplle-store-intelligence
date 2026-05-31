from datetime import date, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import PosLineItem, PosTransaction, SessionZoneVisit, VisitSession, Zone
from app.schemas import (
    ConversionMetrics,
    DepartmentMix,
    EngagementMetrics,
    FootfallMetrics,
    FunnelResponse,
    FunnelStage,
    HourlyMetric,
    MetricsResponse,
    RevenueMetrics,
    ZoneStat,
)


class MetricsService:
    def __init__(self, db: Session):
        self.db = db

    def get_metrics(self, store_id: str | None = None, metric_date: date | None = None) -> MetricsResponse:
        store_id = store_id or settings.store_id
        metric_date = metric_date or date.fromisoformat(settings.operating_date)

        sessions = (
            self.db.query(VisitSession)
            .filter(
                VisitSession.store_id == store_id,
                func.date(VisitSession.started_at) == metric_date,
            )
            .all()
        )

        customer_sessions = [s for s in sessions if s.person_type == "customer"]
        staff_excluded = len([s for s in sessions if s.person_type == "staff"])
        entry_sessions = [s for s in customer_sessions if s.entry_counted]
        engaged = [s for s in customer_sessions if s.is_engaged]
        checkout = [s for s in customer_sessions if s.reached_checkout]
        converted = [s for s in customer_sessions if s.is_converted]

        pos_txns = (
            self.db.query(PosTransaction)
            .filter(
                PosTransaction.store_id == store_id,
                func.date(PosTransaction.transaction_at) == metric_date,
            )
            .all()
        )

        total_nmv = sum(t.nmv or 0 for t in pos_txns)
        pos_count = len(pos_txns)
        unique_sessions = len(customer_sessions)
        matched = len(converted)

        avg_dwell = int(
            sum(s.dwell_total_sec or 0 for s in customer_sessions) / max(len(customer_sessions), 1)
        )
        avg_zones = (
            sum(len(s.zones_visited or []) for s in customer_sessions) / max(len(customer_sessions), 1)
        )

        total_gmv = (
            self.db.query(func.coalesce(func.sum(PosLineItem.nmv), 0))
            .join(PosTransaction, PosLineItem.invoice_number == PosTransaction.invoice_number)
            .filter(PosTransaction.store_id == store_id, func.date(PosTransaction.transaction_at) == metric_date)
            .scalar()
        )
        total_qty = (
            self.db.query(func.coalesce(func.sum(PosLineItem.qty), 0))
            .join(PosTransaction, PosLineItem.invoice_number == PosTransaction.invoice_number)
            .filter(PosTransaction.store_id == store_id, func.date(PosTransaction.transaction_at) == metric_date)
            .scalar()
        )

        hourly = self._hourly_metrics(store_id, metric_date, entry_sessions, pos_txns)
        top_zones = self._top_zones(store_id, metric_date)
        dept_mix = self._department_mix(store_id, metric_date, total_nmv)

        conversion_rate = matched / max(unique_sessions, 1)
        conversion_rate_vs_pos = pos_count / max(unique_sessions, 1)

        return MetricsResponse(
            store_id=store_id,
            store_name=settings.store_name,
            date=str(metric_date),
            footfall=FootfallMetrics(
                total_entries=len(entry_sessions),
                unique_sessions=unique_sessions,
                staff_excluded=staff_excluded,
                re_entries=max(0, len(entry_sessions) - unique_sessions),
            ),
            engagement=EngagementMetrics(
                engaged_visits=len(engaged),
                engagement_rate=round(len(engaged) / max(unique_sessions, 1), 4),
                avg_dwell_sec=avg_dwell,
                avg_zones_per_visit=round(avg_zones, 2),
            ),
            conversion=ConversionMetrics(
                checkout_proximity_visits=len(checkout),
                pos_transactions=pos_count,
                matched_conversions=matched,
                conversion_rate=round(conversion_rate, 4),
                conversion_rate_vs_pos=round(conversion_rate_vs_pos, 4),
                unmatched_pos=max(0, pos_count - matched),
            ),
            revenue=RevenueMetrics(
                total_nmv=round(total_nmv, 2),
                total_gmv=round(float(total_gmv or total_nmv), 2),
                avg_basket_nmv=round(total_nmv / max(pos_count, 1), 2),
                avg_items_per_transaction=round(float(total_qty or 0) / max(pos_count, 1), 2),
                discount_rate=0.225,
                revenue_per_visitor=round(total_nmv / max(unique_sessions, 1), 2),
            ),
            hourly=hourly,
            top_zones=top_zones,
            department_mix=dept_mix,
            computed_at=datetime.utcnow(),
        )

    def get_funnel(self, store_id: str | None = None, metric_date: date | None = None) -> FunnelResponse:
        store_id = store_id or settings.store_id
        metric_date = metric_date or date.fromisoformat(settings.operating_date)

        sessions = (
            self.db.query(VisitSession)
            .filter(
                VisitSession.store_id == store_id,
                func.date(VisitSession.started_at) == metric_date,
                VisitSession.person_type == "customer",
            )
            .all()
        )

        footfall = len([s for s in sessions if s.entry_counted])
        engaged = len([s for s in sessions if s.is_engaged])
        multi_zone = len([s for s in sessions if len(set(s.zones_visited or [])) >= 2])
        checkout = len(
            [s for s in sessions if s.reached_checkout and (s.checkout_dwell_sec or 0) >= settings.checkout_min_sec]
        )
        converted = len([s for s in sessions if s.is_converted])

        counts = [
            ("footfall", footfall, "Valid store entry, staff excluded"),
            ("engaged", engaged, f"Dwell >= {settings.engaged_min_sec}s in product zones or 2+ zones"),
            ("multi_zone", multi_zone, "Visited >= 2 distinct brand/service zones"),
            (
                "checkout_proximity",
                checkout,
                f"Entered CHECKOUT zone with dwell >= {settings.checkout_min_sec}s",
            ),
            ("converted", converted, "POS transaction matched within checkout window"),
        ]

        stages: list[FunnelStage] = []
        top = footfall or 1
        prev = None
        for idx, (stage, count, definition) in enumerate(counts, start=1):
            drop = None if prev is None else round((1 - count / prev) * 100, 1) if prev else 0
            stages.append(
                FunnelStage(
                    stage=stage,
                    stage_order=idx,
                    count=count,
                    pct_of_top=round(count / top * 100, 1),
                    drop_off_from_prev=drop,
                    definition=definition,
                )
            )
            prev = count or prev

        return FunnelResponse(
            store_id=store_id,
            date=str(metric_date),
            stages=stages,
            notes=(
                "Sessions deduplicated; staff excluded; "
                f"re-entry after {settings.reentry_cooldown_sec}s creates new session"
            ),
        )

    def _hourly_metrics(
        self,
        store_id: str,
        metric_date: date,
        entry_sessions: list[VisitSession],
        pos_txns: list[PosTransaction],
    ) -> list[HourlyMetric]:
        hours = sorted(set(
            [s.started_at.strftime("%H") for s in entry_sessions if s.started_at]
            + [t.transaction_at.strftime("%H") for t in pos_txns if t.transaction_at]
        ))

        result = []
        for hour in hours:
            entries = len([s for s in entry_sessions if s.started_at and s.started_at.strftime("%H") == hour])
            hour_txns = [t for t in pos_txns if t.transaction_at.strftime("%H") == hour]
            nmv = sum(t.nmv or 0 for t in hour_txns)
            result.append(
                HourlyMetric(
                    hour=hour,
                    entries=entries,
                    transactions=len(hour_txns),
                    nmv=round(nmv, 2),
                    conversion_rate=round(len(hour_txns) / max(entries, 1), 4),
                )
            )
        return result

    def _top_zones(self, store_id: str, metric_date: date, limit: int = 8) -> list[ZoneStat]:
        rows = (
            self.db.query(
                SessionZoneVisit.zone_id,
                func.count(func.distinct(SessionZoneVisit.session_id)),
                func.coalesce(func.avg(SessionZoneVisit.dwell_sec), 0),
            )
            .join(VisitSession, VisitSession.session_id == SessionZoneVisit.session_id)
            .filter(
                VisitSession.store_id == store_id,
                func.date(VisitSession.started_at) == metric_date,
            )
            .group_by(SessionZoneVisit.zone_id)
            .order_by(func.count(func.distinct(SessionZoneVisit.session_id)).desc())
            .limit(limit)
            .all()
        )

        zone_names = {
            z.zone_id: z.zone_name
            for z in self.db.query(Zone).filter(Zone.store_id == store_id).all()
        }

        return [
            ZoneStat(
                zone_id=row[0],
                zone_name=zone_names.get(row[0], row[0]),
                visits=int(row[1]),
                avg_dwell_sec=int(row[2] or 0),
            )
            for row in rows
        ]

    def _department_mix(self, store_id: str, metric_date: date, total_nmv: float) -> list[DepartmentMix]:
        rows = (
            self.db.query(
                PosLineItem.dep_name,
                func.sum(PosLineItem.nmv),
                func.sum(PosLineItem.qty),
            )
            .join(PosTransaction, PosLineItem.invoice_number == PosTransaction.invoice_number)
            .filter(
                PosTransaction.store_id == store_id,
                func.date(PosTransaction.transaction_at) == metric_date,
            )
            .group_by(PosLineItem.dep_name)
            .order_by(func.sum(PosLineItem.nmv).desc())
            .all()
        )

        return [
            DepartmentMix(
                department=row[0] or "unknown",
                nmv=round(float(row[1] or 0), 2),
                qty=int(row[2] or 0),
                share=round(float(row[1] or 0) / max(total_nmv, 1), 4),
            )
            for row in rows
        ]
