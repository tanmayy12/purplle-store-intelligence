"""Generate realistic tracking events when no CCTV video is available."""

from __future__ import annotations

import csv
import logging
import random
from datetime import datetime, timedelta

from app.config import settings
from app.event_schema import (
    EVENT_DWELL,
    EVENT_ENTRY,
    EVENT_EXIT,
    EVENT_RE_ENTRY,
    EVENT_ZONE_ENTER,
    EVENT_ZONE_EXIT,
    build_event,
    enrich_metadata,
)
from app.publisher import EventPublisher

logger = logging.getLogger(__name__)

BROWSE_ZONES = [
    "FACES_CANADA",
    "GOOD_VIBES",
    "MAYBELLINE",
    "DERMDOC",
    "RENEE_NYBAE",
    "SWISS_BEAUTY",
    "FRAGRANCE_NAIL",
    "MAKEUP_SERVICE",
    "FOH_MAIN",
]


def _load_pos_times() -> list[datetime]:
    times: list[datetime] = []
    try:
        with open(settings.pos_csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            seen: set[str] = set()
            for row in reader:
                inv = row["invoice_number"]
                if inv in seen:
                    continue
                seen.add(inv)
                dt = datetime.strptime(f"{row['order_date']} {row['order_time']}", "%d-%m-%Y %H:%M:%S")
                times.append(dt)
    except FileNotFoundError:
        base = datetime.fromisoformat(f"{settings.operating_date}T12:00:00")
        times = [base + timedelta(minutes=i * 25) for i in range(24)]
    return sorted(times)


def _meta(
    frame_index: int,
    video_time_sec: float,
    visit_number: int = 1,
    **extra,
) -> dict:
    return enrich_metadata(
        extra,
        store_id=settings.store_id,
        camera_id="cam_foh_main",
        frame_index=frame_index,
        video_time_sec=video_time_sec,
        video_source="simulation",
        visit_number=visit_number,
    )


def run_simulation(publisher: EventPublisher) -> int:
    pos_times = _load_pos_times()
    base_date = datetime.fromisoformat(f"{settings.operating_date}T00:00:00")
    random.seed(42)

    total_visitors = max(len(pos_times) * 3, 72)
    event_count = 0
    conversion_idx = 0

    for i in range(total_visitors):
        person_id = str(i + 1)
        hour_offset = random.uniform(0, 9.5)
        entry_time = base_date.replace(hour=12, minute=0, second=0) + timedelta(hours=hour_offset)
        frame_index = int((entry_time - base_date).total_seconds())
        will_convert = i < len(pos_times) + 10

        publisher.publish(
            build_event(
                event_type=EVENT_ENTRY,
                person_id=person_id,
                timestamp=entry_time,
                zone_id="ENTRY_GATE",
                metadata=_meta(frame_index, float(frame_index), visit_number=1, person_type="customer"),
            )
        )
        event_count += 1

        browse_time = entry_time + timedelta(seconds=30)
        for zid in random.sample(BROWSE_ZONES, k=random.randint(1, 3)):
            fi = int((browse_time - base_date).total_seconds())
            publisher.publish(
                build_event(
                    event_type=EVENT_ZONE_ENTER,
                    person_id=person_id,
                    timestamp=browse_time,
                    zone_id=zid,
                    metadata=_meta(fi, float(fi), zone_type="brand"),
                )
            )
            dwell = random.randint(45, 120)
            dwell_time = browse_time + timedelta(seconds=dwell)
            publisher.publish(
                build_event(
                    event_type=EVENT_DWELL,
                    person_id=person_id,
                    timestamp=dwell_time,
                    zone_id=zid,
                    metadata=_meta(fi + dwell, float(fi + dwell), dwell_sec=dwell),
                )
            )
            publisher.publish(
                build_event(
                    event_type=EVENT_ZONE_EXIT,
                    person_id=person_id,
                    timestamp=dwell_time + timedelta(seconds=5),
                    zone_id=zid,
                    metadata=_meta(fi + dwell + 5, float(fi + dwell + 5), dwell_sec=dwell + 5),
                )
            )
            event_count += 3
            browse_time += timedelta(seconds=dwell + 20)

        if will_convert and conversion_idx < len(pos_times):
            checkout_time = pos_times[conversion_idx] - timedelta(minutes=random.randint(2, 8))
            if checkout_time < entry_time:
                checkout_time = entry_time + timedelta(minutes=5)
            fi = int((checkout_time - base_date).total_seconds())
            publisher.publish(
                build_event(
                    event_type=EVENT_ZONE_ENTER,
                    person_id=person_id,
                    timestamp=checkout_time,
                    zone_id="CHECKOUT",
                    metadata=_meta(fi, float(fi), zone_type="checkout"),
                )
            )
            checkout_dwell = random.randint(30, 90)
            publisher.publish(
                build_event(
                    event_type=EVENT_DWELL,
                    person_id=person_id,
                    timestamp=checkout_time + timedelta(seconds=checkout_dwell),
                    zone_id="CHECKOUT",
                    metadata=_meta(fi + checkout_dwell, float(fi + checkout_dwell), dwell_sec=checkout_dwell),
                )
            )
            event_count += 2
            conversion_idx += 1

        exit_time = browse_time + timedelta(minutes=random.randint(2, 12))
        fi = int((exit_time - base_date).total_seconds())
        publisher.publish(
            build_event(
                event_type=EVENT_EXIT,
                person_id=person_id,
                timestamp=exit_time,
                zone_id="EXIT_GATE",
                metadata=_meta(fi, float(fi), dwell_total_sec=int((exit_time - entry_time).total_seconds())),
            )
        )
        event_count += 1

        if i % 15 == 0 and i > 0:
            reentry_time = exit_time + timedelta(seconds=settings.reentry_cooldown_sec + 30)
            fi = int((reentry_time - base_date).total_seconds())
            publisher.publish(
                build_event(
                    event_type=EVENT_RE_ENTRY,
                    person_id=person_id,
                    timestamp=reentry_time,
                    zone_id="ENTRY_GATE",
                    metadata=_meta(fi, float(fi), visit_number=2, is_reentry=True),
                )
            )
            publisher.publish(
                build_event(
                    event_type=EVENT_EXIT,
                    person_id=person_id,
                    timestamp=reentry_time + timedelta(minutes=5),
                    zone_id="EXIT_GATE",
                    metadata=_meta(fi + 300, float(fi + 300), visit_number=2),
                )
            )
            event_count += 2

    publisher.flush()
    logger.info("Simulation published %d canonical events for %d visitors", event_count, total_visitors)
    return event_count
