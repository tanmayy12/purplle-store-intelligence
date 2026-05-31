"""End-to-end CCTV processing pipeline."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

from app.config import settings
from app.detector import PersonDetector
from app.event_builder import EventBuilder
from app.publisher import EventPublisher
from app.video_reader import open_video
from app.zones import load_zone_config

logger = logging.getLogger(__name__)


class CVPipeline:
    def __init__(self, publisher: EventPublisher):
        self.publisher = publisher
        self.detector = PersonDetector(settings.yolo_model)
        self.zone_config = load_zone_config(settings.zones_config_path)
        self.builder = EventBuilder(
            self.zone_config,
            settings.store_id,
            reentry_cooldown_sec=settings.reentry_cooldown_sec,
        )

    def process_video(self, video_path: Path) -> int:
        cap, width, height, fps, total_frames = open_video(video_path)
        if cap is None:
            raise FileNotFoundError(str(video_path))

        self.detector = PersonDetector(settings.yolo_model)
        self.builder = EventBuilder(
            self.zone_config,
            settings.store_id,
            reentry_cooldown_sec=settings.reentry_cooldown_sec,
        )
        base_time = datetime.fromisoformat(f"{settings.operating_date}T12:00:00")
        frame_index = 0
        event_count = 0
        video_source = video_path.name

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_index % settings.frame_skip != 0:
                    frame_index += 1
                    continue

                tracks = self.detector.track_frame(frame, width, height)
                video_time_sec = frame_index / max(fps, 1.0)
                timestamp = base_time + timedelta(seconds=video_time_sec)

                events = self.builder.process_tracks(
                    tracks,
                    timestamp,
                    frame_index,
                    video_time_sec,
                    video_source,
                )
                for event in events:
                    self.publisher.publish(event)
                    event_count += 1

                frame_index += 1
                if frame_index % 500 == 0:
                    pct = (frame_index / total_frames * 100) if total_frames else 0
                    logger.info(
                        "Progress %s: frame %d/%d (%.1f%%), events=%d",
                        video_source,
                        frame_index,
                        total_frames,
                        pct,
                        event_count,
                    )

            final_ts = base_time + timedelta(seconds=frame_index / max(fps, 1.0))
            for event in self.builder.finalize(final_ts, frame_index, frame_index / max(fps, 1.0), video_source):
                self.publisher.publish(event)
                event_count += 1

        finally:
            cap.release()

        stats = self.builder.stats
        logger.info(
            "Finished %s: entries=%d exits=%d re_entries=%d zone_enters=%d zone_exits=%d dwell=%d total_events=%d",
            video_source,
            stats["entries"],
            stats["exits"],
            stats["re_entries"],
            stats["zone_enters"],
            stats["zone_exits"],
            stats["dwell_events"],
            event_count,
        )
        return event_count

    def process_all(self, video_paths: list[Path]) -> int:
        total = 0
        for path in video_paths:
            total += self.process_video(path)
        self.publisher.flush()
        return total
