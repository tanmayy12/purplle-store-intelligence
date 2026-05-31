import os
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Store, Zone

DATABASE_URL = os.getenv("TEST_DATABASE_URL", os.getenv("DATABASE_URL", ""))
pytestmark = pytest.mark.skipif(
    not DATABASE_URL.startswith("postgresql"),
    reason="PostgreSQL required for schema tests (JSONB/ARRAY)",
)


@pytest.fixture
def db_session():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    session.add(
        Store(
            store_id="ST1008",
            store_name="Brigade_Bangalore",
            city="Bangalore",
            operating_date=date(2026, 4, 10),
        )
    )
    session.add(
        Zone(
            zone_id="FACES_CANADA",
            store_id="ST1008",
            zone_name="Faces Canada",
            zone_type="brand",
        )
    )
    session.commit()

    yield session
    session.close()


def test_entry_creates_session(db_session):
    from app.domain.session_engine import SessionEngine

    engine = SessionEngine(db_session)
    event = {
        "event_id": "00000000-0000-0000-0000-000000000001",
        "event_type": "store.entry",
        "timestamp": "2026-04-10T12:00:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 1, "person_type": "customer"},
    }
    result = engine.process_event(event)
    db_session.commit()
    assert result is not None
    assert result.person_type == "customer"
    assert result.entry_counted is True
    assert result.person_id == "ST1008:T1"


def test_zone_enter_updates_zones(db_session):
    from app.domain.session_engine import SessionEngine

    engine = SessionEngine(db_session)
    engine.process_event({
        "event_id": "00000000-0000-0000-0000-000000000002",
        "event_type": "store.entry",
        "timestamp": "2026-04-10T12:00:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 2, "person_type": "customer"},
    })
    engine.process_event({
        "event_id": "00000000-0000-0000-0000-000000000003",
        "event_type": "zone.enter",
        "timestamp": "2026-04-10T12:01:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 2, "zone_id": "FACES_CANADA"},
    })
    db_session.commit()
    from app.models import VisitSession

    session = db_session.query(VisitSession).first()
    assert "FACES_CANADA" in (session.zones_visited or [])


def test_staff_classification(db_session):
    from app.domain.session_engine import SessionEngine

    engine = SessionEngine(db_session)
    engine.process_event({
        "event_id": "00000000-0000-0000-0000-000000000004",
        "event_type": "track.staff_classified",
        "timestamp": "2026-04-10T12:00:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 99, "person_type": "staff"},
    })
    engine.process_event({
        "event_id": "00000000-0000-0000-0000-000000000005",
        "event_type": "store.entry",
        "timestamp": "2026-04-10T12:01:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 99, "person_type": "staff"},
    })
    db_session.commit()
    from app.models import VisitSession

    session = db_session.query(VisitSession).filter(VisitSession.primary_track_id == 99).first()
    assert session.person_type == "staff"
    assert session.entry_counted is False


def test_exit_closes_session(db_session):
    from app.domain.session_engine import SessionEngine

    engine = SessionEngine(db_session)
    engine.process_event({
        "event_id": "00000000-0000-0000-0000-000000000006",
        "event_type": "store.entry",
        "timestamp": "2026-04-10T12:00:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 3, "person_type": "customer"},
    })
    engine.process_event({
        "event_id": "00000000-0000-0000-0000-000000000007",
        "event_type": "store.exit",
        "timestamp": "2026-04-10T12:30:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 3},
    })
    db_session.commit()
    from app.models import VisitSession

    session = db_session.query(VisitSession).filter(VisitSession.primary_track_id == 3).first()
    assert session.ended_at is not None
    assert session.end_reason == "exit"


def test_close_expired_sessions(db_session):
    from app.domain.session_engine import SessionEngine

    engine = SessionEngine(db_session)
    # Create an old session
    engine.process_event({
        "event_id": "00000000-0000-0000-0000-000000000008",
        "event_type": "store.entry",
        "timestamp": "2026-04-10T10:00:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 4, "person_type": "customer"},
    })
    db_session.commit()
    
    # Close expired sessions (current time is 12:00, session is 2 hours old)
    engine.close_expired_sessions()
    db_session.commit()
    
    from app.models import VisitSession
    session = db_session.query(VisitSession).filter(VisitSession.primary_track_id == 4).first()
    assert session.ended_at is not None
    assert session.end_reason == "timeout"


def test_reentry_cooldown(db_session):
    from app.domain.session_engine import SessionEngine

    engine = SessionEngine(db_session)
    # First entry
    engine.process_event({
        "event_id": "00000000-0000-0000-0000-000000000009",
        "event_type": "store.entry",
        "timestamp": "2026-04-10T12:00:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 5, "person_type": "customer"},
    })
    # Exit
    engine.process_event({
        "event_id": "00000000-0000-0000-0000-000000000010",
        "event_type": "store.exit",
        "timestamp": "2026-04-10T12:30:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 5},
    })
    # Re-entry within cooldown (should not create new session)
    engine.process_event({
        "event_id": "00000000-0000-0000-0000-000000000011",
        "event_type": "store.entry",
        "timestamp": "2026-04-10T12:31:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 5, "person_type": "customer"},
    })
    db_session.commit()
    
    from app.models import VisitSession
    sessions = db_session.query(VisitSession).filter(VisitSession.primary_track_id == 5).all()
    # Should have only 1 session (re-entry within cooldown doesn't create new session)
    assert len(sessions) == 1


def test_checkout_detection(db_session):
    from app.domain.session_engine import SessionEngine

    engine = SessionEngine(db_session)
    engine.process_event({
        "event_id": "00000000-0000-0000-0000-000000000012",
        "event_type": "store.entry",
        "timestamp": "2026-04-10T12:00:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 6, "person_type": "customer"},
    })
    engine.process_event({
        "event_id": "00000000-0000-0000-0000-000000000013",
        "event_type": "zone.enter",
        "timestamp": "2026-04-10T12:15:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 6, "zone_id": "CHECKOUT"},
    })
    db_session.commit()
    
    from app.models import VisitSession
    session = db_session.query(VisitSession).filter(VisitSession.primary_track_id == 6).first()
    assert session.reached_checkout is True
    assert session.checkout_dwell_sec > 0


def test_engagement_detection(db_session):
    from app.domain.session_engine import SessionEngine

    engine = SessionEngine(db_session)
    engine.process_event({
        "event_id": "00000000-0000-0000-0000-000000000014",
        "event_type": "store.entry",
        "timestamp": "2026-04-10T12:00:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 7, "person_type": "customer"},
    })
    engine.process_event({
        "event_id": "00000000-0000-0000-0000-000000000015",
        "event_type": "zone.enter",
        "timestamp": "2026-04-10T12:02:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 7, "zone_id": "FACES_CANADA"},
    })
    engine.process_event({
        "event_id": "00000000-0000-0000-0000-000000000016",
        "event_type": "store.exit",
        "timestamp": "2026-04-10T12:30:00Z",
        "store_id": "ST1008",
        "payload": {"track_id": 7},
    })
    db_session.commit()
    
    from app.models import VisitSession
    session = db_session.query(VisitSession).filter(VisitSession.primary_track_id == 7).first()
    assert session.is_engaged is True
    assert session.dwell_total_sec > 60  # More than engaged_min_sec
