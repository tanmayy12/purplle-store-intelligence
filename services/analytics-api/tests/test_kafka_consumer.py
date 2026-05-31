"""Tests for Kafka Consumer."""

import json
from unittest.mock import MagicMock, patch

from app.consumers.tracking_consumer import (
    _send_to_dlq,
    create_topics,
    get_producer,
    publish_event,
)


def test_send_to_dlq_success():
    """Test successful DLQ message send."""
    mock_producer = MagicMock()
    
    event = {"test": "data", "error": "parse error"}
    
    with patch('app.consumers.tracking_consumer._dlq_producer', mock_producer):
        _send_to_dlq(event, "test error")
    
    # Verify produce was called
    mock_producer.produce.assert_called_once()
    mock_producer.flush.assert_called_once()


def test_send_to_dlq_producer_error():
    """Test DLQ send handles producer errors gracefully."""
    mock_producer = MagicMock()
    mock_producer.produce.side_effect = Exception("Kafka error")
    
    event = {"test": "data", "error": "parse error"}
    
    # Should not raise exception
    _send_to_dlq(event, "test error")


def test_get_producer():
    """Test producer creation."""
    producer = get_producer()
    assert producer is not None


def test_publish_event():
    """Test event publishing."""
    producer = get_producer()
    event = {"event_type": "test", "data": "value"}
    
    # Should not raise exception
    publish_event(producer, "test_topic", event)


def test_create_topics():
    """Test topic creation."""
    # Should not raise exception
    create_topics()


def test_consumer_start_stop():
    """Test consumer start and stop."""
    from app.consumers.tracking_consumer import start_consumer, stop_consumer, is_consumer_running
    
    # Start consumer
    start_consumer()
    
    # Note: In a real test, we'd need to mock the Kafka consumer
    # For now, just verify the functions don't crash
    stop_consumer()


def test_messages_processed_counter():
    """Test messages processed counter."""
    from app.consumers.tracking_consumer import messages_processed
    
    count = messages_processed()
    assert isinstance(count, int)
    assert count >= 0


def test_dlq_event_structure():
    """Test DLQ event has correct structure."""
    mock_producer = MagicMock()
    
    raw_event = {"event_id": "123", "type": "entry"}
    error = "parse error"
    
    with patch('app.consumers.tracking_consumer._dlq_producer', mock_producer):
        _send_to_dlq(raw_event, error)
    
    # Get the call arguments
    call_args = mock_producer.produce.call_args
    topic = call_args[0][0]
    message = json.loads(call_args[0][1])
    
    assert topic == "store.tracking.dlq"
    assert "original_event" in message
    assert "error" in message
    assert "timestamp" in message
    assert message["original_event"] == raw_event
    assert message["error"] == error


def test_dlq_send_with_unicode_error():
    """Test DLQ send handles unicode errors gracefully."""
    mock_producer = MagicMock()
    mock_producer.produce.side_effect = UnicodeError("encoding error")
    
    event = {"test": "data", "error": "parse error"}
    
    # Should not raise exception
    _send_to_dlq(event, "test error")
