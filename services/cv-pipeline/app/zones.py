from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Point:
    x: float
    y: float


@dataclass
class LineDef:
    line_id: str
    start: Point
    end: Point
    direction: str
    inward_normal: list[float]
    debounce_frames: int = 5


@dataclass
class ZoneDef:
    zone_id: str
    zone_name: str
    zone_type: str
    priority: int
    is_staff_only: bool
    polygon: list[Point]
    capabilities: dict[str, bool] = field(default_factory=dict)


@dataclass
class ZoneConfig:
    store_id: str
    zones: list[ZoneDef]
    entry_lines: list[LineDef]
    exit_lines: list[LineDef]
    analytics: dict[str, Any]

    def zone_at_point(self, x: float, y: float) -> ZoneDef | None:
        matches = [z for z in self.zones if _point_in_polygon(x, y, z.polygon)]
        if not matches:
            return None
        return sorted(matches, key=lambda z: z.priority, reverse=True)[0]


def _point_in_polygon(x: float, y: float, polygon: list[Point]) -> bool:
    inside = False
    n = len(polygon)
    for i in range(n):
        j = (i + 1) % n
        xi, yi = polygon[i].x, polygon[i].y
        xj, yj = polygon[j].x, polygon[j].y
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
    return inside


def load_zone_config(path: str) -> ZoneConfig:
    import yaml

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    zones = []
    for z in raw.get("zones", []):
        polygon = [Point(**p) for p in z.get("polygon", [])]
        zones.append(
            ZoneDef(
                zone_id=z["zone_id"],
                zone_name=z["zone_name"],
                zone_type=z.get("zone_type", "foh"),
                priority=z.get("priority", 0),
                is_staff_only=z.get("is_staff_only", False),
                polygon=polygon,
                capabilities=z.get("capabilities", {}),
            )
        )

    def _load_lines(key: str) -> list[LineDef]:
        lines = []
        for item in raw.get("lines", {}).get(key, []):
            lines.append(
                LineDef(
                    line_id=item["line_id"],
                    start=Point(**item["start"]),
                    end=Point(**item["end"]),
                    direction=item.get("direction", "inbound"),
                    inward_normal=item.get("inward_normal", [1, 0]),
                    debounce_frames=item.get("debounce_frames", 5),
                )
            )
        return lines

    store = raw.get("store", {})
    return ZoneConfig(
        store_id=store.get("store_id", "ST1008"),
        zones=zones,
        entry_lines=_load_lines("entry_lines"),
        exit_lines=_load_lines("exit_lines"),
        analytics=raw.get("analytics", {}),
    )
