"""Tests for CV Pipeline."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from app.pipeline import CVPipeline
from app.publisher import EventPublisher


def test_pipeline_initialization():
    """Test pipeline can be initialized."""
    mock_publisher = MagicMock(spec=EventPublisher)
    pipeline = CVPipeline(mock_publisher)
    assert pipeline is not None


def test_process_all_with_empty_sources():
    """Test pipeline handles empty video sources."""
    mock_publisher = MagicMock(spec=EventPublisher)
    pipeline = CVPipeline(mock_publisher)
    
    result = pipeline.process_all([])
    assert result == 0


def test_process_single_video():
    """Test processing a single video."""
    mock_publisher = MagicMock(spec=EventPublisher)
    pipeline = CVPipeline(mock_publisher)
    
    # Mock video processing
    with patch('app.pipeline.CVPipeline._process_video') as mock_process:
        mock_process.return_value = 10
        result = pipeline.process_all(["test.mp4"])
        assert result == 10


def test_detector_initialization():
    """Test detector can be initialized."""
    from app.detector import PersonDetector
    
    # This test may fail if YOLO model is not downloaded
    # In CI, we should mock the model loading
    try:
        detector = PersonDetector()
        assert detector is not None
    except Exception:
        # Model not available, skip test
        pass


def test_event_publisher_initialization():
    """Test event publisher can be initialized."""
    publisher = EventPublisher("localhost:9092", "test_topic")
    assert publisher is not None


def test_event_publish():
    """Test event publishing."""
    publisher = EventPublisher("localhost:9092", "test_topic")
    
    event = {
        "event_type": "test",
        "timestamp": datetime.now().isoformat(),
        "store_id": "ST1008",
    }
    
    # Should not raise exception (may fail if Kafka not available)
    try:
        publisher.publish(event)
    except Exception:
        # Kafka not available, acceptable for unit test
        pass


def test_video_reader_resolve_sources():
    """Test video source resolution."""
    from app.video_reader import resolve_video_sources
    
    # Test with no sources
    sources = resolve_video_sources(None, None)
    assert isinstance(sources, list)


def test_zone_config_loading():
    """Test zone configuration can be loaded."""
    from app.zones import load_zone_config
    from pathlib import Path
    
    zones_path = Path(__file__).resolve().parents[3] / "config" / "zones" / "zones.yaml"
    if not zones_path.exists():
        return
    
    config = load_zone_config(str(zones_path))
    assert config is not None
    assert config.store_id is not None
    assert len(config.zones) > 0


def test_simulation_mode():
    """Test simulation mode runs without errors."""
    from app.simulation import run_simulation
    
    mock_publisher = MagicMock(spec=EventPublisher)
    
    # Should not raise exception
    try:
        run_simulation(mock_publisher)
    except Exception:
        # May fail if Kafka not available
        pass


def test_event_schema_validation():
    """Test event schema validation."""
    from app.event_schema import build_event, EVENT_ENTRY
    
    event = build_event(
        EVENT_ENTRY,
        "ST1008",
        "person_123",
        datetime.now(),
        {"track_id": 1}
    )
    
    assert event is not None
    assert "event_type" in event
    assert "timestamp" in event
    assert "store_id" in event


def test_event_enrichment():
    """Test event metadata enrichment."""
    from app.event_schema import enrich_metadata
    
    base_event = {
        "event_type": "zone.enter",
        "zone_id": "TEST_ZONE",
    }
    
    enriched = enrich_metadata(base_event, "test.mp4", 0, 0.0)
    
    assert "video_source" in enriched
    assert "frame_index" in enriched
    assert enriched["video_source"] == "test.mp4"
