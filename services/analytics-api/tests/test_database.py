"""Tests for Database Operations."""

from datetime import date, datetime
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db, run_migrations
from app.models import Base, Store, Zone, Person, VisitSession, Event, Anomaly, PosTransaction


def test_database_connection():
    """Test database connection can be established."""
    db = SessionLocal()
    assert db is not None
    db.close()


def test_get_db_generator():
    """Test get_db is a generator that yields sessions."""
    gen = get_db()
    db = next(gen)
    assert db is not None
    db.close()


def test_run_migrations():
    """Test migrations can be run."""
    # This should not raise any exceptions
    run_migrations()


def test_store_creation(db_session: Session):
    """Test store can be created and retrieved."""
    store = Store(
        store_id="TEST001",
        store_name="Test Store",
        city="Test City",
        operating_date=date(2026, 4, 10),
    )
    db_session.add(store)
    db_session.commit()
    
    retrieved = db_session.query(Store).filter(Store.store_id == "TEST001").first()
    assert retrieved is not None
    assert retrieved.store_name == "Test Store"


def test_zone_creation(db_session: Session):
    """Test zone can be created and retrieved."""
    zone = Zone(
        zone_id="TEST_ZONE",
        store_id="ST1008",
        zone_name="Test Zone",
        zone_type="test",
    )
    db_session.add(zone)
    db_session.commit()
    
    retrieved = db_session.query(Zone).filter(Zone.zone_id == "TEST_ZONE").first()
    assert retrieved is not None
    assert retrieved.zone_name == "Test Zone"


def test_person_creation(db_session: Session):
    """Test person can be created and retrieved."""
    person = Person(
        person_id="ST1008:T999",
        store_id="ST1008",
        person_type="customer",
        first_seen_at=datetime(2026, 4, 10, 12, 0, 0),
        last_seen_at=datetime(2026, 4, 10, 12, 30, 0),
        visit_count=1,
        is_staff=False,
    )
    db_session.add(person)
    db_session.commit()
    
    retrieved = db_session.query(Person).filter(Person.person_id == "ST1008:T999").first()
    assert retrieved is not None
    assert retrieved.person_type == "customer"


def test_session_creation(db_session: Session, sample_person):
    """Test session can be created and retrieved."""
    session = VisitSession(
        store_id="ST1008",
        person_id=sample_person.person_id,
        primary_track_id=999,
        visit_number=1,
        started_at=datetime(2026, 4, 10, 12, 0, 0),
        person_type="customer",
        entry_counted=True,
    )
    db_session.add(session)
    db_session.commit()
    
    retrieved = db_session.query(VisitSession).filter(
        VisitSession.primary_track_id == 999
    ).first()
    assert retrieved is not None
    assert retrieved.person_id == sample_person.person_id


def test_event_creation(db_session: Session, sample_session):
    """Test event can be created and retrieved."""
    event = Event(
        event_id="TEST-EVENT-001",
        store_id="ST1008",
        person_id=sample_session.person_id,
        session_id=sample_session.session_id,
        event_type="store.entry",
        timestamp=datetime(2026, 4, 10, 12, 0, 0),
        metadata={"test": "data"},
    )
    db_session.add(event)
    db_session.commit()
    
    retrieved = db_session.query(Event).filter(Event.event_id == "TEST-EVENT-001").first()
    assert retrieved is not None
    assert retrieved.event_type == "store.entry"


def test_event_jsonb_metadata(db_session: Session, sample_session):
    """Test event can store JSONB metadata."""
    metadata = {
        "track_id": 123,
        "centroid": [0.5, 0.5],
        "confidence": 0.95,
    }
    
    event = Event(
        event_id="TEST-EVENT-002",
        store_id="ST1008",
        person_id=sample_session.person_id,
        session_id=sample_session.session_id,
        event_type="zone.enter",
        timestamp=datetime(2026, 4, 10, 12, 0, 0),
        metadata=metadata,
    )
    db_session.add(event)
    db_session.commit()
    
    retrieved = db_session.query(Event).filter(Event.event_id == "TEST-EVENT-002").first()
    assert retrieved is not None
    assert retrieved.metadata == metadata


def test_session_zones_visited_array(db_session: Session, sample_person):
    """Test session can store zones visited as array."""
    session = VisitSession(
        store_id="ST1008",
        person_id=sample_person.person_id,
        primary_track_id=998,
        visit_number=1,
        started_at=datetime(2026, 4, 10, 12, 0, 0),
        person_type="customer",
        zones_visited=["ZONE_A", "ZONE_B", "ZONE_C"],
    )
    db_session.add(session)
    db_session.commit()
    
    retrieved = db_session.query(VisitSession).filter(
        VisitSession.primary_track_id == 998
    ).first()
    assert retrieved is not None
    assert "ZONE_A" in retrieved.zones_visited
    assert len(retrieved.zones_visited) == 3


def test_cascade_delete_person(db_session: Session):
    """Test deleting person cascades to sessions."""
    person = Person(
        person_id="ST1008:T997",
        store_id="ST1008",
        person_type="customer",
        first_seen_at=datetime(2026, 4, 10, 12, 0, 0),
        last_seen_at=datetime(2026, 4, 10, 12, 30, 0),
        visit_count=1,
    )
    db_session.add(person)
    db_session.commit()
    
    session = VisitSession(
        store_id="ST1008",
        person_id=person.person_id,
        primary_track_id=997,
        visit_number=1,
        started_at=datetime(2026, 4, 10, 12, 0, 0),
        person_type="customer",
    )
    db_session.add(session)
    db_session.commit()
    
    # Delete person
    db_session.delete(person)
    db_session.commit()
    
    # Session should be deleted due to cascade
    retrieved = db_session.query(VisitSession).filter(
        VisitSession.person_id == person.person_id
    ).first()
    assert retrieved is None


def test_cascade_delete_store(db_session: Session):
    """Test deleting store cascades to zones."""
    store = Store(
        store_id="TEST002",
        store_name="Test Store 2",
        city="Test City",
        operating_date=date(2026, 4, 10),
    )
    db_session.add(store)
    db_session.commit()
    
    zone = Zone(
        zone_id="TEST_ZONE2",
        store_id="TEST002",
        zone_name="Test Zone 2",
        zone_type="test",
    )
    db_session.add(zone)
    db_session.commit()
    
    # Delete store
    db_session.delete(store)
    db_session.commit()
    
    # Zone should be deleted due to cascade
    retrieved = db_session.query(Zone).filter(Zone.zone_id == "TEST_ZONE2").first()
    assert retrieved is None
