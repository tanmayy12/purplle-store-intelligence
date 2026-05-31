import os
from datetime import date, datetime
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.models import Base, Store, Zone, PosTransaction, PosLineItem, Person, VisitSession, Event

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://store:CHANGE_ME_STRONG_PASSWORD@localhost:5432/test_store_intelligence"
)

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL.startswith("postgresql"),
    reason="PostgreSQL required for tests (JSONB/ARRAY support)"
)


@pytest.fixture
def db_engine():
    """Create a test database engine."""
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine) -> Generator[Session, None, None]:
    """Create a test database session."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    
    # Add test data
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
            department_map="cosmetics",
        )
    )
    session.add(
        Zone(
            zone_id="CHECKOUT",
            store_id="ST1008",
            zone_name="Checkout",
            zone_type="checkout",
        )
    )
    session.commit()
    
    yield session
    
    session.close()


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Create a test client for FastAPI app."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    from app.database import get_db
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_person(db_session: Session):
    """Create a sample person."""
    person = Person(
        person_id="ST1008:T1",
        store_id="ST1008",
        person_type="customer",
        first_seen_at=datetime(2026, 4, 10, 12, 0, 0),
        last_seen_at=datetime(2026, 4, 10, 12, 30, 0),
        visit_count=1,
        is_staff=False,
    )
    db_session.add(person)
    db_session.commit()
    return person


@pytest.fixture
def sample_session(db_session: Session, sample_person):
    """Create a sample session."""
    session = VisitSession(
        store_id="ST1008",
        person_id=sample_person.person_id,
        primary_track_id=1,
        visit_number=1,
        started_at=datetime(2026, 4, 10, 12, 0, 0),
        ended_at=datetime(2026, 4, 10, 12, 30, 0),
        end_reason="exit",
        person_type="customer",
        entry_counted=True,
        zones_visited=["FACES_CANADA"],
        dwell_total_sec=1800,
        is_engaged=True,
        reached_checkout=True,
        checkout_dwell_sec=300,
        is_converted=True,
        pos_order_id="ORD001",
        invoice_number="INV001",
    )
    db_session.add(session)
    db_session.commit()
    return session


@pytest.fixture
def sample_pos_transaction(db_session: Session):
    """Create a sample POS transaction."""
    transaction = PosTransaction(
        order_id="ORD001",
        store_id="ST1008",
        invoice_number="INV001",
        transaction_time=datetime(2026, 4, 10, 12, 15, 0),
        total_nmv=5000.0,
        total_qty=2,
    )
    db_session.add(transaction)
    db_session.commit()
    
    line_item = PosLineItem(
        line_id="ORD001-L1",
        order_id="ORD001",
        sku="SKU001",
        product_name="Lipstick",
        department="cosmetics",
        nmv=2500.0,
        qty=1,
    )
    db_session.add(line_item)
    db_session.commit()
    
    return transaction
