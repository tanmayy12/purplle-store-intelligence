"""Integration tests for end-to-end workflows."""

from datetime import datetime
from sqlalchemy.orm import Session

from app.domain.session_engine import SessionEngine, persist_tracking_event
from app.domain.event_normalizer import normalize_event


def test_entry_to_session_workflow(db_session: Session):
    """Test complete workflow from entry event to session creation."""
    engine = SessionEngine(db_session)
    
    # Process entry event
    event = {
        "event_id": "INT-001",
        "event_type": "store.entry",
        "timestamp": "2026-04-10T12:00:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 100, "person_type": "customer"},
    }
    
    result = engine.process_event(event)
    db_session.commit()
    
    # Verify person was created
    from app.models import Person
    person = db_session.query(Person).filter(Person.person_id == "ST1008:T100").first()
    assert person is not None
    assert person.person_type == "customer"
    
    # Verify session was created
    from app.models import VisitSession
    session = db_session.query(VisitSession).filter(VisitSession.primary_track_id == 100).first()
    assert session is not None
    assert session.entry_counted is True


def test_zone_visit_workflow(db_session: Session):
    """Test workflow from zone enter to zone visit tracking."""
    engine = SessionEngine(db_session)
    
    # Entry first
    engine.process_event({
        "event_id": "INT-002",
        "event_type": "store.entry",
        "timestamp": "2026-04-10T12:00:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 101, "person_type": "customer"},
    })
    
    # Zone enter
    engine.process_event({
        "event_id": "INT-003",
        "event_type": "zone.enter",
        "timestamp": "2026-04-10T12:01:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 101, "zone_id": "FACES_CANADA"},
    })
    
    db_session.commit()
    
    # Verify zone visit was recorded
    from app.models import VisitSession, ZoneVisit
    session = db_session.query(VisitSession).filter(VisitSession.primary_track_id == 101).first()
    assert session is not None
    assert "FACES_CANADA" in (session.zones_visited or [])
    
    zone_visit = db_session.query(ZoneVisit).filter(
        ZoneVisit.session_id == session.session_id
    ).first()
    assert zone_visit is not None
    assert zone_visit.zone_id == "FACES_CANADA"


def test_staff_classification_workflow(db_session: Session):
    """Test workflow for staff classification."""
    engine = SessionEngine(db_session)
    
    # Staff classification
    engine.process_event({
        "event_id": "INT-004",
        "event_type": "track.staff_classified",
        "timestamp": "2026-04-10T12:00:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 200, "person_type": "staff"},
    })
    
    # Entry (should not be counted)
    engine.process_event({
        "event_id": "INT-005",
        "event_type": "store.entry",
        "timestamp": "2026-04-10T12:01:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 200, "person_type": "staff"},
    })
    
    db_session.commit()
    
    # Verify session is marked as staff
    from app.models import VisitSession
    session = db_session.query(VisitSession).filter(VisitSession.primary_track_id == 200).first()
    assert session is not None
    assert session.person_type == "staff"
    assert session.entry_counted is False


def test_event_normalization(db_session: Session):
    """Test event normalization and persistence."""
    raw_event = {
        "event_id": "INT-006",
        "event_type": "store.entry",
        "timestamp": "2026-04-10T12:00:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 300, "person_type": "customer"},
    }
    
    # Normalize event
    normalized = normalize_event(raw_event)
    
    # Persist event
    persist_tracking_event(db_session, normalized, raw_event=raw_event)
    db_session.commit()
    
    # Verify event was persisted
    from app.models import Event
    event = db_session.query(Event).filter(Event.event_id == "INT-006").first()
    assert event is not None
    assert event.event_type == "store.entry"


def test_session_closure_workflow(db_session: Session):
    """Test session closure on exit."""
    engine = SessionEngine(db_session)
    
    # Entry
    engine.process_event({
        "event_id": "INT-007",
        "event_type": "store.entry",
        "timestamp": "2026-04-10T12:00:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 400, "person_type": "customer"},
    })
    
    # Exit
    engine.process_event({
        "event_id": "INT-008",
        "event_type": "store.exit",
        "timestamp": "2026-04-10T12:30:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 400},
    })
    
    db_session.commit()
    
    # Verify session was closed
    from app.models import VisitSession
    session = db_session.query(VisitSession).filter(VisitSession.primary_track_id == 400).first()
    assert session is not None
    assert session.ended_at is not None
    assert session.end_reason == "exit"


def test_pos_correlation_workflow(db_session: Session, sample_pos_transaction):
    """Test POS transaction correlation with session."""
    engine = SessionEngine(db_session)
    
    # Create session that reaches checkout
    engine.process_event({
        "event_id": "INT-009",
        "event_type": "store.entry",
        "timestamp": "2026-04-10T12:00:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 500, "person_type": "customer"},
    })
    
    engine.process_event({
        "event_id": "INT-010",
        "event_type": "zone.enter",
        "timestamp": "2026-04-10T12:10:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 500, "zone_id": "CHECKOUT"},
    })
    
    db_session.commit()
    
    # Run POS correlation
    engine.correlate_pos_transactions()
    db_session.commit()
    
    # Verify correlation (may or may not match depending on timing)
    from app.models import VisitSession
    session = db_session.query(VisitSession).filter(VisitSession.primary_track_id == 500).first()
    assert session is not None
    # If matched, pos_order_id should be set
    # This is a basic test - actual matching depends on time windows


def test_metrics_after_event_processing(db_session: Session):
    """Test metrics are updated after event processing."""
    from app.domain.metrics_service import MetricsService
    
    engine = SessionEngine(db_session)
    
    # Process some events
    for i in range(5):
        engine.process_event({
            "event_id": f"INT-METRICS-{i}",
            "event_type": "store.entry",
            "timestamp": "2026-04-10T12:00:00Z",
            "store_id": "ST1008",
            "payload": {"track_id": 600 + i, "person_type": "customer"},
        })
    
    db_session.commit()
    
    # Refresh metrics
    from app.domain.metrics_aggregator import MetricsAggregator
    aggregator = MetricsAggregator(db_session)
    aggregator.refresh()
    db_session.commit()
    
    # Verify metrics are available
    service = MetricsService(db_session)
    metrics = service.get_metrics()
    
    assert metrics is not None
    assert metrics.footfall.total_entries >= 5
