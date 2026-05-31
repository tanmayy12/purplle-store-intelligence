from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.metrics_service import MetricsService
from app.models import StoreMetric, VisitSession


class MetricsAggregator:
    """Persist precomputed daily/hourly aggregates into the metrics table."""

    def __init__(self, db: Session):
        self.db = db
        self.metrics_service = MetricsService(db)

    def upsert_daily(self, store_id: str | None = None, metric_date: date | None = None) -> StoreMetric:
        store_id = store_id or settings.store_id
        metric_date = metric_date or date.fromisoformat(settings.operating_date)
        snapshot = self.metrics_service.get_metrics(store_id=store_id, metric_date=metric_date)

        row = (
            self.db.query(StoreMetric)
            .filter(
                StoreMetric.store_id == store_id,
                StoreMetric.metric_date == metric_date,
                StoreMetric.granularity == "daily",
                StoreMetric.metric_hour.is_(None),
            )
            .first()
        )
        if not row:
            row = StoreMetric(
                store_id=store_id,
                metric_date=metric_date,
                granularity="daily",
                metric_hour=None,
            )
            self.db.add(row)

        row.total_entries = snapshot.footfall.total_entries
        row.unique_sessions = snapshot.footfall.unique_sessions
        row.staff_excluded = snapshot.footfall.staff_excluded
        row.engaged_visits = snapshot.engagement.engaged_visits
        row.checkout_visits = snapshot.conversion.checkout_proximity_visits
        row.conversions = snapshot.conversion.matched_conversions
        row.conversion_rate = snapshot.conversion.conversion_rate
        row.total_nmv = snapshot.revenue.total_nmv
        row.avg_dwell_sec = snapshot.engagement.avg_dwell_sec
        row.avg_basket_nmv = snapshot.revenue.avg_basket_nmv
        row.pos_transactions = snapshot.conversion.pos_transactions
        row.payload = {
            "hourly": [h.model_dump() for h in snapshot.hourly],
            "top_zones": [z.model_dump() for z in snapshot.top_zones],
            "department_mix": [d.model_dump() for d in snapshot.department_mix],
        }
        row.computed_at = datetime.utcnow()
        return row

    def upsert_hourly(self, store_id: str | None = None, metric_date: date | None = None) -> list[StoreMetric]:
        store_id = store_id or settings.store_id
        metric_date = metric_date or date.fromisoformat(settings.operating_date)
        snapshot = self.metrics_service.get_metrics(store_id=store_id, metric_date=metric_date)
        rows: list[StoreMetric] = []

        for hour_metric in snapshot.hourly:
            hour = int(hour_metric.hour)
            row = (
                self.db.query(StoreMetric)
                .filter(
                    StoreMetric.store_id == store_id,
                    StoreMetric.metric_date == metric_date,
                    StoreMetric.granularity == "hourly",
                    StoreMetric.metric_hour == hour,
                )
                .first()
            )
            if not row:
                row = StoreMetric(
                    store_id=store_id,
                    metric_date=metric_date,
                    granularity="hourly",
                    metric_hour=hour,
                )
                self.db.add(row)

            row.total_entries = hour_metric.entries
            row.pos_transactions = hour_metric.transactions
            row.total_nmv = hour_metric.nmv
            row.conversion_rate = hour_metric.conversion_rate
            row.computed_at = datetime.utcnow()
            rows.append(row)

        return rows

    def refresh(self, store_id: str | None = None, metric_date: date | None = None) -> None:
        self.upsert_daily(store_id=store_id, metric_date=metric_date)
        self.upsert_hourly(store_id=store_id, metric_date=metric_date)
        self.db.commit()

    @staticmethod
    def count_sessions_for_date(db: Session, store_id: str, metric_date: date) -> int:
        return (
            db.query(func.count(VisitSession.session_id))
            .filter(
                VisitSession.store_id == store_id,
                func.date(VisitSession.started_at) == metric_date,
            )
            .scalar()
            or 0
        )
