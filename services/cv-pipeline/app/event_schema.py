"""Canonical CV event schema for Kafka."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any


EVENT_ENTRY = "entry"
EVENT_EXIT = "exit"
EVENT_RE_ENTRY = "re_entry"
EVENT_ZONE_ENTER = "zone_enter"
EVENT_ZONE_EXIT = "zone_exit"
EVENT_DWELL = "dwell"
EVENT_STAFF = "staff_classified"


def build_event(
    *,
    event_type: str,
    person_id: str,
    timestamp: datetime,
    zone_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Kafka event using the required schema."""
    meta = metadata or {}
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": timestamp.isoformat() + "Z",
        "person_id": person_id,
        "event_type": event_type,
        "zone_id": zone_id,
        "metadata": meta,
    }


def enrich_metadata(
    base: dict[str, Any],
    *,
    store_id: str,
    camera_id: str,
    frame_index: int,
    video_time_sec: float,
    video_source: str,
    confidence: float | None = None,
    bbox: list[float] | None = None,
    centroid: tuple[float, float] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    meta = dict(base)
    meta.update(
        {
            "store_id": store_id,
            "camera_id": camera_id,
            "frame_index": frame_index,
            "video_time_sec": round(video_time_sec, 3),
            "video_source": video_source,
        }
    )
    if confidence is not None:
        meta["confidence"] = round(confidence, 4)
    if bbox is not None:
        meta["bbox"] = bbox
    if centroid is not None:
        meta["centroid"] = {"x": round(centroid[0], 4), "y": round(centroid[1], 4)}
    meta.update(extra)
    return meta
