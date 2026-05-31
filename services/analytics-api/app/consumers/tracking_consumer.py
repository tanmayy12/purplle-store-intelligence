import json
import logging
import threading
import time
from typing import Any

from confluent_kafka import Consumer, KafkaException, Producer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.domain.anomaly_detector import AnomalyDetector
from app.domain.metrics_aggregator import MetricsAggregator
from app.domain.event_normalizer import normalize_event
from app.domain.session_engine import SessionEngine, persist_tracking_event

logger = logging.getLogger(__name__)

_dlq_producer: Producer | None = None

_consumer_thread: threading.Thread | None = None
_consumer_running = False
_stop_event = threading.Event()
_messages_processed = 0


def is_consumer_running() -> bool:
    return _consumer_running


def messages_processed() -> int:
    return _messages_processed


def start_consumer() -> None:
    global _consumer_thread, _consumer_running
    if _consumer_thread and _consumer_thread.is_alive():
        return
    _stop_event.clear()
    _consumer_thread = threading.Thread(target=_consume_loop, name="kafka-consumer", daemon=True)
    _consumer_thread.start()


def stop_consumer() -> None:
    _stop_event.set()
    if _consumer_thread:
        _consumer_thread.join(timeout=10)


def _send_to_dlq(raw_event: dict[str, Any], error: str) -> None:
    """Send failed event to Dead Letter Queue."""
    global _dlq_producer
    try:
        if _dlq_producer is None:
            _dlq_producer = get_producer()
        
        dlq_event = {
            "original_event": raw_event,
            "error": error,
            "timestamp": time.time(),
            "topic": settings.kafka_topic_raw,
        }
        _dlq_producer.produce(
            settings.kafka_topic_dlq,
            json.dumps(dlq_event).encode("utf-8")
        )
        _dlq_producer.flush()
        logger.warning("Sent failed event to DLQ: %s", error)
    except Exception as exc:
        logger.error("Failed to send event to DLQ: %s", exc)


def _consume_loop() -> None:
    global _consumer_running, _messages_processed
    
    # Exponential backoff for Kafka connection
    retry_delay = settings.kafka_retry_initial_delay_sec
    max_delay = settings.kafka_retry_max_delay_sec
    max_attempts = settings.kafka_retry_max_attempts
    
    for attempt in range(max_attempts):
        try:
            consumer = Consumer(
                {
                    "bootstrap.servers": settings.kafka_bootstrap,
                    "group.id": settings.kafka_group_id,
                    "auto.offset.reset": "earliest",
                    "enable.auto.commit": True,
                }
            )
            consumer.subscribe([settings.kafka_topic_raw, settings.kafka_topic_anomalies])
            _consumer_running = True
            logger.info("Kafka consumer started on topics: %s (attempt %d)", settings.kafka_topic_raw, attempt + 1)
            break
        except KafkaException as exc:
            if attempt == max_attempts - 1:
                logger.error("Failed to connect to Kafka after %d attempts: %s", max_attempts, exc)
                raise
            logger.warning("Kafka connection failed (attempt %d/%d), retrying in %ds: %s", attempt + 1, max_attempts, retry_delay, exc)
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay)
    else:
        return  # Failed to connect after all retries

    session_engine: SessionEngine | None = None
    db: Session | None = None

    try:
        while not _stop_event.is_set():
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.warning("Kafka consumer error: %s", msg.error())
                continue

            try:
                raw_event: dict[str, Any] = json.loads(msg.value().decode("utf-8"))
                event_data = normalize_event(raw_event)
            except (json.JSONDecodeError, AttributeError) as exc:
                logger.error("Invalid Kafka message: %s", exc)
                # Send to DLQ for inspection
                try:
                    _send_to_dlq({"raw": msg.value().decode("utf-8", errors="ignore")}, str(exc))
                except Exception:
                    pass  # Best effort DLQ send
                continue

            if db is None:
                db = SessionLocal()
                session_engine = SessionEngine(db)

            persist_tracking_event(db, event_data, raw_event=raw_event)
            session_engine.process_event(event_data)
            db.commit()
            _messages_processed += 1

            if _messages_processed % 50 == 0:
                session_engine.close_expired_sessions()
                session_engine.correlate_pos_transactions()
                MetricsAggregator(db).refresh()
                db.commit()
    except KafkaException as exc:
        logger.exception("Kafka consumer failed: %s", exc)
    finally:
        _consumer_running = False
        if db and session_engine:
            session_engine.close_expired_sessions()
            session_engine.correlate_pos_transactions()
            detector = AnomalyDetector(db)
            detector.run_hourly_checks()
            detector.detect_loitering()
            MetricsAggregator(db).refresh()
            db.commit()
            db.close()
        consumer.close()
        logger.info("Kafka consumer stopped. Processed %d messages", _messages_processed)


def create_topics() -> None:
    from confluent_kafka.admin import AdminClient, NewTopic

    admin = AdminClient({"bootstrap.servers": settings.kafka_bootstrap})
    topics = [
        NewTopic(settings.kafka_topic_raw, num_partitions=1, replication_factor=1),
        NewTopic(settings.kafka_topic_anomalies, num_partitions=1, replication_factor=1),
        NewTopic(settings.kafka_topic_session, num_partitions=1, replication_factor=1),
        NewTopic(settings.kafka_topic_dlq, num_partitions=1, replication_factor=1),
    ]
    futures = admin.create_topics(topics)
    for topic, future in futures.items():
        try:
            future.result()
            logger.info("Created topic: %s", topic)
        except Exception as exc:
            logger.info("Topic %s may already exist: %s", topic, exc)


def get_producer() -> Producer:
    return Producer({"bootstrap.servers": settings.kafka_bootstrap})


def publish_event(producer: Producer, topic: str, event: dict[str, Any]) -> None:
    producer.produce(topic, json.dumps(event).encode("utf-8"))
    producer.flush()
