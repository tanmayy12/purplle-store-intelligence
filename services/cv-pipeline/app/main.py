import logging
import os
import sys
import time
from pathlib import Path

from app.config import settings
from app.pipeline import CVPipeline
from app.publisher import EventPublisher
from app.simulation import run_simulation
from app.video_reader import resolve_video_sources

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def wait_for_kafka(max_retries: int = 30, delay: float = 2.0) -> None:
    from confluent_kafka import Producer

    for attempt in range(max_retries):
        try:
            producer = Producer({"bootstrap.servers": settings.kafka_bootstrap})
            producer.list_topics(timeout=5)
            logger.info("Kafka is ready")
            return
        except Exception as exc:
            logger.info("Waiting for Kafka (%d/%d): %s", attempt + 1, max_retries, exc)
            time.sleep(delay)
    raise RuntimeError("Kafka not available")


def main() -> None:
    logger.info("CV Pipeline starting for store %s", settings.store_id)
    wait_for_kafka()
    publisher = EventPublisher(settings.kafka_bootstrap, settings.kafka_topic_raw)

    video_sources = resolve_video_sources(settings.video_path, settings.video_dir)
    use_simulation = settings.simulation_mode == "always" or (
        settings.simulation_mode == "auto" and not video_sources
    )

    if use_simulation:
        logger.warning(
            "No CCTV files found (path=%s dir=%s) — running simulation",
            settings.video_path,
            settings.video_dir,
        )
        run_simulation(publisher)
    else:
        pipeline = CVPipeline(publisher)
        total_events = pipeline.process_all(video_sources)
        logger.info("Processed %d video(s), published %d events", len(video_sources), total_events)

    logger.info("CV Pipeline finished successfully")
    sys.exit(0)


if __name__ == "__main__":
    main()
