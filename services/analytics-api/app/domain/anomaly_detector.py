import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Anomaly, Person, PosTransaction, VisitSession

logger = logging.getLogger(__name__)


class AnomalyDetector:
    def __init__(self, db: Session):
        self.db = db

    def run_hourly_checks(self, metric_date: datetime | None = None) -> list[Anomaly]:
        created: list[Anomaly] = []
        base_date = metric_date or datetime.fromisoformat(settings.operating_date)
        hourly_stats = self._hourly_conversion_stats(base_date.date())

        if len(hourly_stats) < 2:
            return created

        rates = [h["rate"] for h in hourly_stats if h["entries"] >= 5]
        if not rates:
            return created

        mean_rate = sum(rates) / len(rates)
        for stat in hourly_stats:
            if stat["entries"] < 5:
                continue
            if stat["rate"] < mean_rate * 0.5 and stat["entries"] > 0:
                created.append(
                    self._create(
                        anomaly_type="conversion_rate_drop",
                        severity="high",
                        detected_at=datetime.combine(base_date.date(), datetime.min.time()).replace(
                            hour=int(stat["hour"])
                        ),
                        description=(
                            f"Hour {stat['hour']}: conversion rate {stat['rate']:.1%} "
                            f"below 50% of daily average ({mean_rate:.1%})"
                        ),
                        evidence=stat,
                    )
                )
            if stat["entries"] > stat["mean_entries"] * 2 and stat["transactions"] == 0:
                created.append(
                    self._create(
                        anomaly_type="footfall_spike_no_conversion",
                        severity="high",
                        detected_at=datetime.combine(base_date.date(), datetime.min.time()).replace(
                            hour=int(stat["hour"])
                        ),
                        description=f"Hour {stat['hour']}: footfall spike with zero POS transactions",
                        evidence=stat,
                    )
                )

        self.db.commit()
        return created

    def detect_loitering(self) -> list[Anomaly]:
        created: list[Anomaly] = []
        threshold = timedelta(minutes=20)
        sessions = (
            self.db.query(VisitSession)
            .filter(
                VisitSession.store_id == settings.store_id,
                VisitSession.person_type == "customer",
                VisitSession.dwell_total_sec >= threshold.total_seconds(),
                VisitSession.is_converted.is_(False),
            )
            .all()
        )
        for session in sessions:
            zones = session.zones_visited or []
            if len(set(zones)) <= 1 and "FOH_MAIN" in zones:
                created.append(
                    self._create(
                        anomaly_type="loitering",
                        severity="medium",
                        detected_at=session.ended_at or session.started_at,
                        person_id=session.person_id,
                        zone_id="FOH_MAIN",
                        session_id=session.session_id,
                        description="Extended FOH dwell without zone progression",
                        evidence={
                            "dwell_sec": session.dwell_total_sec,
                            "track_id": session.primary_track_id,
                        },
                    )
                )
        self.db.commit()
        return created

    def _hourly_conversion_stats(self, metric_date) -> list[dict[str, Any]]:
        sessions = (
            self.db.query(VisitSession)
            .filter(
                VisitSession.store_id == settings.store_id,
                func.date(VisitSession.started_at) == metric_date,
                VisitSession.person_type == "customer",
                VisitSession.entry_counted.is_(True),
            )
            .all()
        )
        txns = (
            self.db.query(PosTransaction)
            .filter(
                PosTransaction.store_id == settings.store_id,
                func.date(PosTransaction.transaction_at) == metric_date,
            )
            .all()
        )

        hours = sorted(set(
            [s.started_at.strftime("%H") for s in sessions if s.started_at]
            + [t.transaction_at.strftime("%H") for t in txns if t.transaction_at]
        ))

        entry_counts = [len([s for s in sessions if s.started_at.strftime("%H") == h]) for h in hours]
        mean_entries = sum(entry_counts) / max(len(entry_counts), 1)

        stats = []
        for hour in hours:
            entries = len([s for s in sessions if s.started_at.strftime("%H") == hour])
            transactions = len([t for t in txns if t.transaction_at.strftime("%H") == hour])
            stats.append(
                {
                    "hour": hour,
                    "entries": entries,
                    "transactions": transactions,
                    "rate": transactions / max(entries, 1),
                    "mean_entries": mean_entries,
                }
            )
        return stats

    def _resolve_track_id(self, person_id: str | None) -> int | None:
        if not person_id:
            return None
        person = self.db.get(Person, person_id)
        return person.last_track_id if person else None

    def _create(
        self,
        anomaly_type: str,
        severity: str,
        detected_at: datetime,
        description: str,
        evidence: dict[str, Any] | None = None,
        person_id: str | None = None,
        zone_id: str | None = None,
        session_id: uuid.UUID | None = None,
    ) -> Anomaly:
        if evidence is None:
            evidence = {}
        if person_id and "track_id" not in evidence:
            track_id = self._resolve_track_id(person_id)
            if track_id is not None:
                evidence = {**evidence, "track_id": track_id}

        anomaly = Anomaly(
            anomaly_id=uuid.uuid4(),
            store_id=settings.store_id,
            anomaly_type=anomaly_type,
            severity=severity,
            detected_at=detected_at,
            person_id=person_id,
            zone_id=zone_id,
            session_id=session_id,
            description=description,
            evidence=evidence,
        )
        self.db.add(anomaly)
        return anomaly
