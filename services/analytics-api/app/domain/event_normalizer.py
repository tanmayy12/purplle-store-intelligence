"""Normalize CV pipeline events to internal analytics format."""

from __future__ import annotations

from typing import Any


EVENT_TYPE_MAP = {
    "entry": "store.entry",
    "re_entry": "store.entry",
    "exit": "store.exit",
    "zone_enter": "zone.enter",
    "zone_exit": "zone.exit",
    "dwell": "zone.dwell",
    "staff_classified": "track.staff_classified",
    "store.entry": "store.entry",
    "store.exit": "store.exit",
    "zone.enter": "zone.enter",
    "zone.exit": "zone.exit",
    "zone.dwell": "zone.dwell",
    "track.staff_classified": "track.staff_classified",
    "track.heartbeat": "track.heartbeat",
}


def is_canonical_event(event: dict[str, Any]) -> bool:
    return "person_id" in event and "metadata" in event


def normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    if not is_canonical_event(event):
        return event

    meta = event.get("metadata") or {}
    person_id = event.get("person_id", "")
    track_id = _parse_track_id(person_id)
    internal_type = EVENT_TYPE_MAP.get(event.get("event_type", ""), event.get("event_type", ""))

    payload: dict[str, Any] = {
        "track_id": track_id,
        "person_id": person_id,
        "zone_id": event.get("zone_id") or meta.get("zone_id"),
        "person_type": meta.get("person_type", "customer"),
    }

    for key in (
        "confidence",
        "bbox",
        "centroid",
        "dwell_sec",
        "dwell_total_sec",
        "visit_number",
        "is_reentry",
        "entry_line",
        "exit_reason",
        "zone_type",
        "zone_name",
        "reason",
    ):
        if key in meta:
            payload[key] = meta[key]

    if event.get("event_type") == "re_entry":
        payload["is_reentry"] = True

    if internal_type == "track.staff_classified":
        payload["person_type"] = "staff"

    return {
        "event_id": event.get("event_id"),
        "event_type": internal_type,
        "event_version": "2.0",
        "store_id": meta.get("store_id", "ST1008"),
        "camera_id": meta.get("camera_id", "cam_foh_main"),
        "timestamp": event.get("timestamp"),
        "frame_index": meta.get("frame_index", 0),
        "video_time_sec": meta.get("video_time_sec", 0),
        "source": "cv-pipeline",
        "payload": payload,
    }


def _parse_track_id(person_id: str) -> int | None:
    try:
        return int(str(person_id).replace("staff_", ""))
    except (TypeError, ValueError):
        return None
