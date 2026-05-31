from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.config import settings
from app.event_schema import (
    EVENT_DWELL,
    EVENT_ENTRY,
    EVENT_EXIT,
    EVENT_RE_ENTRY,
    EVENT_STAFF,
    EVENT_ZONE_ENTER,
    EVENT_ZONE_EXIT,
    build_event,
    enrich_metadata,
)
from app.zones import LineDef, ZoneConfig

logger = logging.getLogger(__name__)

ENTRY_ZONE = "ENTRY_GATE"
EXIT_ZONE = "EXIT_GATE"
DWELL_EMIT_INTERVAL_SEC = 30


@dataclass
class TrackState:
    track_id: int
    person_id: str
    last_centroid: tuple[float, float]
    prev_centroid: tuple[float, float] | None = None
    inside_store: bool = False
    entry_time: datetime | None = None
    last_exit_time: datetime | None = None
    visit_number: int = 0
    person_type: str = "customer"
    current_zones: set[str] = field(default_factory=set)
    zone_enter_times: dict[str, datetime] = field(default_factory=dict)
    last_dwell_emit: dict[str, datetime] = field(default_factory=dict)
    staff_zone_frames: int = 0
    entry_debounce: int = 0
    exit_debounce: int = 0
    last_seen: datetime | None = None
    lost_since: datetime | None = None


class EventBuilder:
    """Convert ByteTrack detections into canonical JSON events."""

    def __init__(
        self,
        zone_config: ZoneConfig,
        store_id: str,
        camera_id: str = "cam_foh_main",
        reentry_cooldown_sec: int = 120,
    ):
        self.zone_config = zone_config
        self.store_id = store_id
        self.camera_id = camera_id
        self.reentry_cooldown_sec = reentry_cooldown_sec
        self.track_states: dict[int, TrackState] = {}
        self.stats = {
            "entries": 0,
            "exits": 0,
            "re_entries": 0,
            "zone_enters": 0,
            "zone_exits": 0,
            "dwell_events": 0,
        }

    def process_tracks(
        self,
        tracks: list[dict[str, Any]],
        timestamp: datetime,
        frame_index: int,
        video_time_sec: float,
        video_source: str,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        seen: set[int] = set()

        # Filter tracks by confidence threshold
        filtered_tracks = [
            track for track in tracks
            if track.get("confidence", 0.0) >= settings.detection_confidence_threshold
        ]

        for track in filtered_tracks:
            track_id = int(track["track_id"])
            person_id = str(track.get("person_id", track_id))
            cx, cy = track["centroid"]
            seen.add(track_id)

            state = self.track_states.get(track_id)
            if state is None:
                state = TrackState(
                    track_id=track_id,
                    person_id=person_id,
                    last_centroid=(cx, cy),
                    last_seen=timestamp,
                )
                self.track_states[track_id] = state
            else:
                # Track recovered after loss
                if state.lost_since is not None:
                    logger.debug("Track %d recovered after %.1fs", track_id, (timestamp - state.lost_since).total_seconds())
                    state.lost_since = None

            state.prev_centroid = state.last_centroid
            state.last_centroid = (cx, cy)
            state.last_seen = timestamp
            state.person_id = person_id

            events.extend(
                self._line_crossings(state, track, timestamp, frame_index, video_time_sec, video_source)
            )
            events.extend(
                self._zone_transitions(state, track, cx, cy, timestamp, frame_index, video_time_sec, video_source)
            )

        # Track loss handling with timeout
        for track_id in list(self.track_states.keys()):
            if track_id not in seen:
                state = self.track_states[track_id]
                state.last_seen = state.last_seen or timestamp
                
                if state.lost_since is None:
                    # First frame where track is lost
                    state.lost_since = timestamp
                    logger.debug("Track %d lost at %.1fs", track_id, video_time_sec)
                    continue
                
                # Check if timeout exceeded
                time_since_loss = (timestamp - state.lost_since).total_seconds()
                if time_since_loss < settings.track_loss_timeout_sec:
                    # Still within timeout window, wait for recovery
                    continue
                
                # Timeout exceeded, treat as exit
                logger.debug("Track %d lost timeout exceeded (%.1fs), emitting exit", track_id, time_since_loss)
                self.track_states.pop(track_id)
                if state.inside_store:
                    events.append(
                        self._make_exit_event(
                            state,
                            timestamp,
                            frame_index,
                            video_time_sec,
                            video_source,
                            reason="track_lost_timeout",
                            bbox=None,
                            confidence=0.0,
                        )
                    )

        return events

    def finalize(self, timestamp: datetime, frame_index: int, video_time_sec: float, video_source: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for track_id, state in list(self.track_states.items()):
            for zone_id in list(state.current_zones):
                events.extend(
                    self._emit_zone_exit(
                        state,
                        zone_id,
                        state.last_centroid[0],
                        state.last_centroid[1],
                        timestamp,
                        frame_index,
                        video_time_sec,
                        video_source,
                        bbox=None,
                        confidence=0.0,
                    )
                )
            if state.inside_store:
                events.append(
                    self._make_exit_event(
                        state,
                        timestamp,
                        frame_index,
                        video_time_sec,
                        video_source,
                        reason="video_end",
                        bbox=None,
                        confidence=0.0,
                    )
                )
            self.track_states.pop(track_id, None)
        return events

    def _line_crossings(
        self,
        state: TrackState,
        track: dict[str, Any],
        timestamp: datetime,
        frame_index: int,
        video_time_sec: float,
        video_source: str,
    ) -> list[dict[str, Any]]:
        if state.prev_centroid is None:
            return []

        events: list[dict[str, Any]] = []
        cx, cy = state.last_centroid

        for line in self.zone_config.entry_lines:
            crossed, direction = _line_crossed(state.prev_centroid, state.last_centroid, line)
            if not crossed:
                continue

            if direction == "inbound":
                if state.inside_store:
                    continue
                state.entry_debounce += 1
                if state.entry_debounce < line.debounce_frames:
                    continue
                state.entry_debounce = 0

                is_reentry = (
                    state.last_exit_time is not None
                    and (timestamp - state.last_exit_time).total_seconds() > self.reentry_cooldown_sec
                )
                resume_visit = (
                    state.last_exit_time is not None
                    and (timestamp - state.last_exit_time).total_seconds() <= self.reentry_cooldown_sec
                )

                if resume_visit:
                    state.inside_store = True
                    state.entry_time = state.entry_time or timestamp
                    logger.debug("Person %s resumed visit within cooldown", state.person_id)
                    continue

                state.inside_store = True
                state.entry_time = timestamp
                state.visit_number += 1

                if is_reentry:
                    event_type = EVENT_RE_ENTRY
                    self.stats["re_entries"] += 1
                else:
                    event_type = EVENT_ENTRY
                    self.stats["entries"] += 1

                events.append(
                    build_event(
                        event_type=event_type,
                        person_id=state.person_id,
                        timestamp=timestamp,
                        zone_id=ENTRY_ZONE,
                        metadata=enrich_metadata(
                            {},
                            store_id=self.store_id,
                            camera_id=self.camera_id,
                            frame_index=frame_index,
                            video_time_sec=video_time_sec,
                            video_source=video_source,
                            confidence=track.get("confidence", 0.0),
                            bbox=track.get("bbox"),
                            centroid=(cx, cy),
                            person_type=state.person_type,
                            visit_number=state.visit_number,
                            entry_line=line.line_id,
                            is_reentry=is_reentry,
                        ),
                    )
                )

            elif direction == "outbound" and state.inside_store:
                state.exit_debounce += 1
                if state.exit_debounce < line.debounce_frames:
                    continue
                state.exit_debounce = 0
                events.append(
                    self._make_exit_event(
                        state,
                        timestamp,
                        frame_index,
                        video_time_sec,
                        video_source,
                        reason="line_crossing",
                        bbox=track.get("bbox"),
                        confidence=track.get("confidence", 0.0),
                    )
                )

        return events

    def _make_exit_event(
        self,
        state: TrackState,
        timestamp: datetime,
        frame_index: int,
        video_time_sec: float,
        video_source: str,
        reason: str,
        bbox: list[float] | None,
        confidence: float,
    ) -> dict[str, Any]:
        dwell_total = 0
        if state.entry_time:
            dwell_total = int((timestamp - state.entry_time).total_seconds())

        state.inside_store = False
        state.last_exit_time = timestamp
        self.stats["exits"] += 1

        return build_event(
            event_type=EVENT_EXIT,
            person_id=state.person_id,
            timestamp=timestamp,
            zone_id=EXIT_ZONE,
            metadata=enrich_metadata(
                {},
                store_id=self.store_id,
                camera_id=self.camera_id,
                frame_index=frame_index,
                video_time_sec=video_time_sec,
                video_source=video_source,
                confidence=confidence,
                bbox=bbox,
                centroid=state.last_centroid,
                person_type=state.person_type,
                visit_number=state.visit_number,
                dwell_total_sec=dwell_total,
                exit_reason=reason,
            ),
        )

    def _zone_transitions(
        self,
        state: TrackState,
        track: dict[str, Any],
        cx: float,
        cy: float,
        timestamp: datetime,
        frame_index: int,
        video_time_sec: float,
        video_source: str,
    ) -> list[dict[str, Any]]:
        if not state.inside_store:
            return []

        zone = self.zone_config.zone_at_point(cx, cy)
        current = {zone.zone_id} if zone else set()
        events: list[dict[str, Any]] = []

        for zone_id in state.current_zones - current:
            events.extend(
                self._emit_zone_exit(
                    state,
                    zone_id,
                    cx,
                    cy,
                    timestamp,
                    frame_index,
                    video_time_sec,
                    video_source,
                    track.get("bbox"),
                    track.get("confidence", 0.0),
                )
            )

        for zone_id in current - state.current_zones:
            state.zone_enter_times[zone_id] = timestamp
            state.last_dwell_emit[zone_id] = timestamp
            zdef = next(z for z in self.zone_config.zones if z.zone_id == zone_id)
            self.stats["zone_enters"] += 1

            events.append(
                build_event(
                    event_type=EVENT_ZONE_ENTER,
                    person_id=state.person_id,
                    timestamp=timestamp,
                    zone_id=zone_id,
                    metadata=enrich_metadata(
                        {},
                        store_id=self.store_id,
                        camera_id=self.camera_id,
                        frame_index=frame_index,
                        video_time_sec=video_time_sec,
                        video_source=video_source,
                        confidence=track.get("confidence", 0.0),
                        bbox=track.get("bbox"),
                        centroid=(cx, cy),
                        zone_type=zdef.zone_type,
                        zone_name=zdef.zone_name,
                        visit_number=state.visit_number,
                    ),
                )
            )

            if zdef.is_staff_only and state.person_type == "customer":
                state.staff_zone_frames += 1
                if state.staff_zone_frames >= settings.staff_zone_dwell_threshold_frames:
                    state.person_type = "staff"
                    events.append(
                        build_event(
                            event_type=EVENT_STAFF,
                            person_id=state.person_id,
                            timestamp=timestamp,
                            zone_id=zone_id,
                            metadata=enrich_metadata(
                                {},
                                store_id=self.store_id,
                                camera_id=self.camera_id,
                                frame_index=frame_index,
                                video_time_sec=video_time_sec,
                                video_source=video_source,
                                reason="dwell_in_staff_zone",
                            ),
                        )
                    )

        for zone_id in current & state.current_zones:
            entered_at = state.zone_enter_times.get(zone_id, timestamp)
            dwell_sec = int((timestamp - entered_at).total_seconds())
            last_emit = state.last_dwell_emit.get(zone_id, entered_at)
            if dwell_sec >= DWELL_EMIT_INTERVAL_SEC and (timestamp - last_emit).total_seconds() >= DWELL_EMIT_INTERVAL_SEC:
                state.last_dwell_emit[zone_id] = timestamp
                self.stats["dwell_events"] += 1
                events.append(
                    build_event(
                        event_type=EVENT_DWELL,
                        person_id=state.person_id,
                        timestamp=timestamp,
                        zone_id=zone_id,
                        metadata=enrich_metadata(
                            {},
                            store_id=self.store_id,
                            camera_id=self.camera_id,
                            frame_index=frame_index,
                            video_time_sec=video_time_sec,
                            video_source=video_source,
                            dwell_sec=dwell_sec,
                            visit_number=state.visit_number,
                        ),
                    )
                )

        state.current_zones = current
        return events

    def _emit_zone_exit(
        self,
        state: TrackState,
        zone_id: str,
        cx: float,
        cy: float,
        timestamp: datetime,
        frame_index: int,
        video_time_sec: float,
        video_source: str,
        bbox: list[float] | None,
        confidence: float,
    ) -> list[dict[str, Any]]:
        entered_at = state.zone_enter_times.pop(zone_id, timestamp)
        state.last_dwell_emit.pop(zone_id, None)
        dwell_sec = int((timestamp - entered_at).total_seconds())
        self.stats["zone_exits"] += 1

        return [
            build_event(
                event_type=EVENT_ZONE_EXIT,
                person_id=state.person_id,
                timestamp=timestamp,
                zone_id=zone_id,
                metadata=enrich_metadata(
                    {},
                    store_id=self.store_id,
                    camera_id=self.camera_id,
                    frame_index=frame_index,
                    video_time_sec=video_time_sec,
                    video_source=video_source,
                    confidence=confidence,
                    bbox=bbox,
                    centroid=(cx, cy),
                    dwell_sec=dwell_sec,
                    visit_number=state.visit_number,
                ),
            )
        ]


def _line_crossed(
    p1: tuple[float, float],
    p2: tuple[float, float],
    line: LineDef,
) -> tuple[bool, str | None]:
    x1, y1 = p1
    x2, y2 = p2
    lx1, ly1 = line.start.x, line.start.y
    lx2, ly2 = line.end.x, line.end.y

    def side(x: float, y: float) -> float:
        return (lx2 - lx1) * (y - ly1) - (ly2 - ly1) * (x - lx1)

    s1 = side(x1, y1)
    s2 = side(x2, y2)
    if s1 * s2 >= 0:
        return False, None

    nx, ny = line.inward_normal
    movement_x = x2 - x1
    dot = movement_x * nx + (y2 - y1) * ny
    if line.direction == "inbound":
        return True, "inbound" if dot > 0 else "outbound"
    return True, "outbound" if dot < 0 else "inbound"
