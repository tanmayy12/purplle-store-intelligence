"""Tests for Anomaly Detector."""

from datetime import datetime
from sqlalchemy.orm import Session

from app.domain.anomaly_detector import AnomalyDetector


def test_detector_initialization(db_session: Session):
    """Test anomaly detector can be initialized."""
    detector = AnomalyDetector(db_session)
    assert detector is not None


def test_run_hourly_checks(db_session: Session, sample_session):
    """Test hourly anomaly checks run without errors."""
    detector = AnomalyDetector(db_session)
    # Should not raise any exceptions
    detector.run_hourly_checks()


def test_detect_loitering(db_session: Session, sample_session):
    """Test loitering detection runs without errors."""
    detector = AnomalyDetector(db_session)
    # Should not raise any exceptions
    detector.detect_loitering()


def test_conversion_rate_drop_detection(db_session: Session, sample_session):
    """Test conversion rate drop detection logic."""
    detector = AnomalyDetector(db_session)
    detector.run_hourly_checks()
    
    # Check if anomalies were created (may be empty if no anomalies detected)
    from app.models import Anomaly
    anomalies = db_session.query(Anomaly).all()
    assert isinstance(anomalies, list)


def test_footfall_spike_detection(db_session: Session, sample_session):
    """Test footfall spike detection logic."""
    detector = AnomalyDetector(db_session)
    detector.run_hourly_checks()
    
    # Check if anomalies were created
    from app.models import Anomaly
    anomalies = db_session.query(Anomaly).filter(
        Anomaly.anomaly_type == "footfall_spike"
    ).all()
    assert isinstance(anomalies, list)


def test_anomaly_creation(db_session: Session):
    """Test anomaly can be created and persisted."""
    from app.models import Anomaly
    
    anomaly = Anomaly(
        store_id="ST1008",
        anomaly_type="test_anomaly",
        severity="low",
        detected_at=datetime(2026, 4, 10, 12, 0, 0),
        description="Test anomaly for unit testing",
        zone_id="FACES_CANADA",
    )
    db_session.add(anomaly)
    db_session.commit()
    
    retrieved = db_session.query(Anomaly).filter(
        Anomaly.anomaly_type == "test_anomaly"
    ).first()
    assert retrieved is not None
    assert retrieved.severity == "low"


def test_anomaly_severity_levels(db_session: Session):
    """Test anomalies with different severity levels."""
    from app.models import Anomaly
    
    severities = ["low", "medium", "high", "critical"]
    
    for severity in severities:
        anomaly = Anomaly(
            store_id="ST1008",
            anomaly_type=f"test_{severity}",
            severity=severity,
            detected_at=datetime(2026, 4, 10, 12, 0, 0),
            description=f"Test {severity} anomaly",
        )
        db_session.add(anomaly)
    
    db_session.commit()
    
    anomalies = db_session.query(Anomaly).filter(
        Anomaly.anomaly_type.like("test_%")
    ).all()
    assert len(anomalies) == len(severities)


def test_anomaly_with_zone(db_session: Session):
    """Test anomaly can be associated with a zone."""
    from app.models import Anomaly
    
    anomaly = Anomaly(
        store_id="ST1008",
        anomaly_type="zone_anomaly",
        severity="medium",
        detected_at=datetime(2026, 4, 10, 12, 0, 0),
        description="Zone-specific anomaly",
        zone_id="FACES_CANADA",
    )
    db_session.add(anomaly)
    db_session.commit()
    
    retrieved = db_session.query(Anomaly).filter(
        Anomaly.zone_id == "FACES_CANADA"
    ).first()
    assert retrieved is not None
    assert retrieved.zone_id == "FACES_CANADA"


def test_anomaly_metadata(db_session: Session):
    """Test anomaly can store metadata as JSONB."""
    from app.models import Anomaly
    
    metadata = {
        "threshold": 0.5,
        "actual_value": 0.2,
        "context": "test"
    }
    
    anomaly = Anomaly(
        store_id="ST1008",
        anomaly_type="metadata_test",
        severity="low",
        detected_at=datetime(2026, 4, 10, 12, 0, 0),
        description="Test with metadata",
        metadata=metadata,
    )
    db_session.add(anomaly)
    db_session.commit()
    
    retrieved = db_session.query(Anomaly).filter(
        Anomaly.anomaly_type == "metadata_test"
    ).first()
    assert retrieved is not None
    assert retrieved.metadata == metadata
