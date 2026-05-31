import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from dateutil import parser as date_parser
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Anomaly,
    Person,
    PosTransaction,
    SessionZoneVisit,
    TrackingEvent,
    VisitSession,
)

logger = logging.getLogger(__name__)

CHECKOUT_ZONE = "CHECKOUT"
STAFF_ZONE_PREFIX = "STAFF_"


def person_id_for_track(store_id: str, track_id: int) -> str:
    return f"{store_id}:T{track_id}"


class SessionEngine:
    def __init__(self, db: Session):
        self.db = db
        self.active_sessions: dict[int, VisitSession] = {}
        self.track_exit_times: dict[int, datetime] = {}
        self.staff_tracks: set[int] = set()

    def process_event(self, event_data: dict[str, Any]) -> VisitSession | None:
        event_type = event_data.get("event_type")
        payload = event_data.get("payload", {})
        track_id = payload.get("track_id") or event_data.get("track_id")
        timestamp = self._parse_ts(event_data.get("timestamp"))
        store_id = event_data.get("store_id", settings.store_id)

        if event_type == "track.staff_classified":
            if track_id is not None:
                self.staff_tracks.add(track_id)
                person = self._get_or_create_person(store_id, track_id, timestamp, person_type="staff")
                person.is_staff = True
                person.person_type = "staff"
                session = self.active_sessions.get(track_id)
                if session:
                    session.person_type = "staff"
                    session.entry_counted = False
            return None

        if track_id is None:
            return None

        if event_type == "store.entry":
            return self._handle_entry(track_id, timestamp, store_id, payload)

        if event_type == "store.exit":
            return self._handle_exit(track_id, timestamp, payload)

        session = self.active_sessions.get(track_id)
        if not session:
            return None

        if event_type in ("zone.enter", "zone.exit", "zone.dwell"):
            self._handle_zone_event(session, event_type, timestamp, payload)

        return session

    def _get_or_create_person(
        self,
        store_id: str,
        track_id: int,
        timestamp: datetime,
        person_type: str = "customer",
    ) -> Person:
        pid = person_id_for_track(store_id, track_id)
        person = self.db.get(Person, pid)
        if person:
            person.last_seen_at = timestamp
            person.last_track_id = track_id
            if person_type == "staff":
                person.person_type = "staff"
                person.is_staff = True
            return person

        person = Person(
            person_id=pid,
            store_id=store_id,
            person_type=person_type,
            first_seen_at=timestamp,
            last_seen_at=timestamp,
            visit_count=0,
            is_staff=person_type == "staff",
            last_track_id=track_id,
        )
        self.db.add(person)
        return person

    def _handle_entry(
        self, track_id: int, timestamp: datetime, store_id: str, payload: dict[str, Any]
    ) -> VisitSession:
        person_type = payload.get("person_type", "customer")
        if track_id in self.staff_tracks or person_type == "staff":
            self.staff_tracks.add(track_id)
            person_type = "staff"

        person = self._get_or_create_person(store_id, track_id, timestamp, person_type=person_type)

        last_exit = self.track_exit_times.get(track_id)
        if not payload.get("is_reentry") and last_exit and (timestamp - last_exit).total_seconds() <= settings.reentry_cooldown_sec:
            session = self.active_sessions.get(track_id)
            if session:
                session.ended_at = None
                session.end_reason = None
                person.last_seen_at = timestamp
                return session

        person.visit_count = (person.visit_count or 0) + 1
        person.last_seen_at = timestamp

        session = VisitSession(
            session_id=uuid.uuid4(),
            store_id=store_id,
            person_id=person.person_id,
            primary_track_id=track_id,
            visit_number=person.visit_count,
            started_at=timestamp,
            person_type=person_type,
            entry_counted=person_type == "customer",
            zones_visited=[],
        )
        self.active_sessions[track_id] = session
        self.db.add(session)
        return session

    def _handle_exit(self, track_id: int, timestamp: datetime, payload: dict[str, Any]) -> VisitSession | None:
        session = self.active_sessions.pop(track_id, None)
        if not session:
            return None

        session.ended_at = timestamp
        session.end_reason = "exit"
        dwell = payload.get("dwell_total_sec")
        if dwell:
            session.dwell_total_sec = int(dwell)
        elif session.started_at:
            session.dwell_total_sec = int((timestamp - session.started_at).total_seconds())

        person = self.db.get(Person, session.person_id)
        if person:
            person.last_seen_at = timestamp

        self._finalize_session(session)
        self.track_exit_times[track_id] = timestamp
        return session

    def _handle_zone_event(
        self, session: VisitSession, event_type: str, timestamp: datetime, payload: dict[str, Any]
    ) -> None:
        zone_id = payload.get("zone_id")
        if not zone_id:
            return

        zones = list(session.zones_visited or [])
        if zone_id not in zones:
            zones.append(zone_id)
            session.zones_visited = zones

        if zone_id == CHECKOUT_ZONE:
            session.reached_checkout = True
            if event_type == "zone.dwell":
                dwell = int(payload.get("dwell_sec", 0))
                session.checkout_dwell_sec = max(session.checkout_dwell_sec or 0, dwell)

        if zone_id.startswith(STAFF_ZONE_PREFIX) and session.person_type == "customer":
            self._create_anomaly(
                anomaly_type="customer_in_staff_zone",
                severity="medium",
                detected_at=timestamp,
                person_id=session.person_id,
                zone_id=zone_id,
                session_id=session.session_id,
                description=f"Customer entered staff zone {zone_id}",
                evidence={"dwell_sec": payload.get("dwell_sec", 0), "track_id": session.primary_track_id},
            )

        if event_type == "zone.enter":
            visit = SessionZoneVisit(
                session_id=session.session_id,
                person_id=session.person_id,
                zone_id=zone_id,
                entered_at=timestamp,
            )
            self.db.add(visit)
        elif event_type == "zone.exit":
            visit = (
                self.db.query(SessionZoneVisit)
                .filter(
                    SessionZoneVisit.session_id == session.session_id,
                    SessionZoneVisit.zone_id == zone_id,
                    SessionZoneVisit.exited_at.is_(None),
                )
                .order_by(SessionZoneVisit.entered_at.desc())
                .first()
            )
            if visit:
                visit.exited_at = timestamp
                dwell = payload.get("dwell_sec")
                if dwell is not None:
                    visit.dwell_sec = int(dwell)
                elif visit.entered_at:
                    visit.dwell_sec = int((timestamp - visit.entered_at).total_seconds())

    def _finalize_session(self, session: VisitSession) -> None:
        total_dwell = (
            self.db.query(SessionZoneVisit)
            .filter(SessionZoneVisit.session_id == session.session_id)
            .with_entities(SessionZoneVisit.dwell_sec)
            .all()
        )
        product_dwell = sum(v[0] or 0 for v in total_dwell)
        if session.dwell_total_sec == 0:
            session.dwell_total_sec = product_dwell

        session.is_engaged = product_dwell >= settings.engaged_min_sec or len(session.zones_visited or []) >= 2
        session.max_funnel_stage = self._compute_funnel_stage(session)

        if (
            session.started_at
            and session.ended_at
            and (session.ended_at - session.started_at).total_seconds() <= settings.bounce_threshold_sec
            and not session.is_engaged
        ):
            session.entry_counted = False

    def _compute_funnel_stage(self, session: VisitSession) -> str:
        if session.is_converted:
            return "converted"
        if session.reached_checkout and (session.checkout_dwell_sec or 0) >= settings.checkout_min_sec:
            return "checkout_proximity"
        zones = session.zones_visited or []
        if len(set(zones)) >= 2:
            return "multi_zone"
        if session.is_engaged:
            return "engaged"
        if session.entry_counted:
            return "footfall"
        return "bounce"

    def close_expired_sessions(self, now: datetime | None = None) -> int:
        from datetime import timezone
        now = now or datetime.now(timezone.utc)
        closed = 0
        expired_tracks = []
        for track_id, session in self.active_sessions.items():
            if session.started_at and (now - session.started_at).total_seconds() > settings.session_timeout_sec:
                expired_tracks.append(track_id)

        for track_id in expired_tracks:
            session = self.active_sessions.pop(track_id)
            session.ended_at = now
            session.end_reason = "timeout"
            self._finalize_session(session)
            closed += 1
        return closed

    def correlate_pos_transactions(self) -> int:
        unmatched = (
            self.db.query(PosTransaction)
            .filter(PosTransaction.store_id == settings.store_id)
            .all()
        )
        matched = 0
        for txn in unmatched:
            window_start = txn.transaction_at - timedelta(seconds=settings.pos_match_window_before_sec)
            window_end = txn.transaction_at + timedelta(seconds=settings.pos_match_window_after_sec)
            candidates = (
                self.db.query(VisitSession)
                .filter(
                    VisitSession.store_id == settings.store_id,
                    VisitSession.reached_checkout.is_(True),
                    VisitSession.is_converted.is_(False),
                    VisitSession.person_type == "customer",
                    VisitSession.started_at <= window_end,
                )
                .all()
            )
            best = None
            best_delta = None
            for session in candidates:
                end_time = session.ended_at or session.started_at
                if end_time < window_start:
                    continue
                delta = abs((end_time - txn.transaction_at).total_seconds())
                if best is None or delta < best_delta:
                    best = session
                    best_delta = delta

            if best and best_delta is not None and best_delta <= settings.pos_match_window_before_sec:
                best.is_converted = True
                best.pos_order_id = txn.order_id
                best.invoice_number = txn.invoice_number
                best.max_funnel_stage = "converted"
                matched += 1
            else:
                existing = (
                    self.db.query(Anomaly)
                    .filter(
                        Anomaly.anomaly_type == "unmatched_pos_transaction",
                        Anomaly.description.contains(txn.invoice_number),
                    )
                    .first()
                )
                if not existing:
                    self._create_anomaly(
                        anomaly_type="unmatched_pos_transaction",
                        severity="medium",
                        detected_at=txn.transaction_at,
                        person_id=None,
                        zone_id=CHECKOUT_ZONE,
                        session_id=None,
                        description=f"No checkout session matched for invoice {txn.invoice_number}",
                        evidence={"invoice_number": txn.invoice_number, "order_id": txn.order_id},
                    )
        self.db.commit()
        return matched

    def _create_anomaly(
        self,
        anomaly_type: str,
        severity: str,
        detected_at: datetime,
        person_id: str | None,
        zone_id: str | None,
        session_id: UUID | None,
        description: str,
        evidence: dict[str, Any] | None,
    ) -> None:
        anomaly = Anomaly(
            anomaly_id=uuid.uuid4(),
            store_id=settings.store_id,
            person_id=person_id,
            anomaly_type=anomaly_type,
            severity=severity,
            detected_at=detected_at,
            zone_id=zone_id,
            session_id=session_id,
            description=description,
            evidence=evidence,
        )
        self.db.add(anomaly)

    @staticmethod
    def _parse_ts(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        return date_parser.isoparse(str(value))


def persist_tracking_event(
    db: Session,
    event_data: dict[str, Any],
    raw_event: dict[str, Any] | None = None,
) -> TrackingEvent:
    payload = event_data.get("payload", {})
    stored_payload = raw_event if raw_event else payload
    zone_id = event_data.get("zone_id") or payload.get("zone_id")
    store_id = event_data.get("store_id", settings.store_id)
    track_id = payload.get("track_id") or event_data.get("track_id")
    timestamp = SessionEngine._parse_ts(event_data["timestamp"])

    person_id = payload.get("person_id")
    if not person_id and track_id is not None:
        person_id = person_id_for_track(store_id, int(track_id))
    if not person_id:
        raise ValueError("Event requires track_id or person_id for persistence")

    person = db.get(Person, person_id)
    if not person:
        person = Person(
            person_id=person_id,
            store_id=store_id,
            person_type=payload.get("person_type", "customer"),
            first_seen_at=timestamp,
            last_seen_at=timestamp,
            visit_count=0,
            last_track_id=int(track_id) if track_id is not None else None,
        )
        db.add(person)
    else:
        person.last_seen_at = timestamp
        if track_id is not None:
            person.last_track_id = int(track_id)

    session_id = None
    if payload.get("session_id"):
        session_id = uuid.UUID(str(payload["session_id"]))

    metadata = stored_payload if isinstance(stored_payload, dict) else {"raw": stored_payload}
    if track_id is not None and "track_id" not in metadata:
        metadata = {**metadata, "track_id": track_id}

    event = TrackingEvent(
        event_id=uuid.UUID(str(event_data["event_id"])),
        store_id=store_id,
        person_id=person_id,
        session_id=session_id,
        event_type=event_data["event_type"],
        canonical_type=metadata.get("event_type") if isinstance(metadata, dict) else None,
        timestamp=timestamp,
        zone_id=zone_id,
        metadata_json=metadata,
    )
    db.add(event)
    return event
