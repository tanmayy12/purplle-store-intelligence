import json
import logging
from typing import Any

from confluent_kafka import Producer

logger = logging.getLogger(__name__)


class EventPublisher:
    """Kafka producer for CV pipeline events."""

    def __init__(self, bootstrap: str, topic: str):
        self.producer = Producer({"bootstrap.servers": bootstrap})
        self.topic = topic
        self.published = 0

    def publish(self, event: dict[str, Any]) -> None:
        key = event.get("person_id") or event.get("metadata", {}).get("store_id", "ST1008")
        self.producer.produce(
            self.topic,
            json.dumps(event).encode("utf-8"),
            key=str(key),
        )
        self.published += 1
        if self.published % 100 == 0:
            self.producer.flush()

    def flush(self) -> None:
        self.producer.flush()
        logger.info("Published %d events to topic %s", self.published, self.topic)
