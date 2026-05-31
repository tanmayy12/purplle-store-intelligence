from datetime import datetime

from app.event_builder import EventBuilder, _line_crossed
from app.event_schema import EVENT_ENTRY, EVENT_EXIT, EVENT_RE_ENTRY, EVENT_ZONE_ENTER
from app.zones import LineDef, Point, ZoneConfig, ZoneDef, load_zone_config


def _minimal_config() -> ZoneConfig:
    entry_line = LineDef(
        line_id="main_entrance_in",
        start=Point(0.07, 0.34),
        end=Point(0.07, 0.66),
        direction="inbound",
        inward_normal=[1, 0],
        debounce_frames=1,
    )
    foh = ZoneDef(
        zone_id="FOH_MAIN",
        zone_name="FOH",
        zone_type="foh",
        priority=10,
        is_staff_only=False,
        polygon=[Point(0.1, 0.2), Point(0.9, 0.2), Point(0.9, 0.8), Point(0.1, 0.8)],
    )
    return ZoneConfig(
        store_id="ST1008",
        zones=[foh],
        entry_lines=[entry_line],
        exit_lines=[],
        analytics={},
    )


def test_line_crossing_inbound():
    line = LineDef(
        line_id="test",
        start=Point(0.07, 0.34),
        end=Point(0.07, 0.66),
        direction="inbound",
        inward_normal=[1, 0],
        debounce_frames=1,
    )
    crossed, direction = _line_crossed((0.05, 0.5), (0.09, 0.5), line)
    assert crossed is True
    assert direction == "inbound"


def test_entry_event_emitted():
    builder = EventBuilder(_minimal_config(), "ST1008", reentry_cooldown_sec=120)
    ts = datetime(2026, 4, 10, 12, 0, 0)
    tracks = [{"track_id": 1, "person_id": "1", "centroid": (0.05, 0.5), "bbox": [], "confidence": 0.9}]
    builder.process_tracks(tracks, ts, 0, 0.0, "test.mp4")
    tracks[0]["centroid"] = (0.09, 0.5)
    events = builder.process_tracks(tracks, ts, 1, 0.04, "test.mp4")
    entry_events = [e for e in events if e["event_type"] == EVENT_ENTRY]
    assert len(entry_events) == 1
    assert entry_events[0]["person_id"] == "1"
    assert entry_events[0]["zone_id"] == "ENTRY_GATE"
    assert "timestamp" in entry_events[0]
    assert "metadata" in entry_events[0]


def test_exit_after_entry():
    builder = EventBuilder(_minimal_config(), "ST1008", reentry_cooldown_sec=120)
    ts = datetime(2026, 4, 10, 12, 0, 0)
    tracks = [{"track_id": 2, "person_id": "2", "centroid": (0.05, 0.5), "bbox": [], "confidence": 0.9}]
    builder.process_tracks(tracks, ts, 0, 0.0, "test.mp4")
    tracks[0]["centroid"] = (0.09, 0.5)
    builder.process_tracks(tracks, ts, 1, 0.04, "test.mp4")
    tracks[0]["centroid"] = (0.05, 0.5)
    events = builder.process_tracks(tracks, ts, 2, 0.08, "test.mp4")
    exit_events = [e for e in events if e["event_type"] == EVENT_EXIT]
    assert len(exit_events) >= 1


def test_reentry_after_cooldown():
    builder = EventBuilder(_minimal_config(), "ST1008", reentry_cooldown_sec=60)
    ts = datetime(2026, 4, 10, 12, 0, 0)
    tracks = [{"track_id": 3, "person_id": "3", "centroid": (0.05, 0.5), "bbox": [], "confidence": 0.9}]

    builder.process_tracks(tracks, ts, 0, 0.0, "test.mp4")
    tracks[0]["centroid"] = (0.09, 0.5)
    builder.process_tracks(tracks, ts, 1, 0.04, "test.mp4")
    tracks[0]["centroid"] = (0.05, 0.5)
    builder.process_tracks(tracks, ts, 2, 0.08, "test.mp4")

    tracks[0]["centroid"] = (0.05, 0.5)
    reentry_ts = ts + __import__("datetime").timedelta(seconds=90)
    events = builder.process_tracks(tracks, reentry_ts, 3, 0.12, "test.mp4")
    tracks[0]["centroid"] = (0.09, 0.5)
    events += builder.process_tracks(tracks, reentry_ts, 4, 0.16, "test.mp4")
    reentry = [e for e in events if e["event_type"] == EVENT_RE_ENTRY]
    assert len(reentry) >= 1


def test_zone_enter_inside_store():
    builder = EventBuilder(_minimal_config(), "ST1008")
    ts = datetime(2026, 4, 10, 12, 0, 0)
    state = builder.track_states
    tracks_in = [{"track_id": 4, "person_id": "4", "centroid": (0.05, 0.5), "bbox": [], "confidence": 0.9}]
    builder.process_tracks(tracks_in, ts, 0, 0.0, "test.mp4")
    tracks_in[0]["centroid"] = (0.09, 0.5)
    builder.process_tracks(tracks_in, ts, 1, 0.04, "test.mp4")

    tracks = [{"track_id": 4, "person_id": "4", "centroid": (0.5, 0.5), "bbox": [], "confidence": 0.9}]
    events = builder.process_tracks(tracks, ts, 2, 0.08, "test.mp4")
    zone_events = [e for e in events if e["event_type"] == EVENT_ZONE_ENTER]
    assert any(e["zone_id"] == "FOH_MAIN" for e in zone_events)


def test_load_production_zones():
    from pathlib import Path

    zones_path = Path(__file__).resolve().parents[3] / "config" / "zones" / "zones.yaml"
    if not zones_path.exists():
        return
    config = load_zone_config(str(zones_path))
    assert len(config.zones) >= 30
    assert len(config.entry_lines) >= 1
