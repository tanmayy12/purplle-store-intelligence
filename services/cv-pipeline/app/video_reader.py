from __future__ import annotations

import logging
import os
from pathlib import Path

import cv2

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".m4v"}


def discover_videos(video_path: str, video_dir: str) -> list[Path]:
    """Resolve one or more CCTV files from a file path and/or directory."""
    found: list[Path] = []

    if video_path:
        path = Path(video_path)
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            found.append(path.resolve())

    if video_dir:
        directory = Path(video_dir)
        if directory.is_dir():
            for ext in VIDEO_EXTENSIONS:
                found.extend(sorted(directory.rglob(f"*{ext}")))

    # De-duplicate while preserving order
    seen: set[str] = set()
    unique: list[Path] = []
    for path in found:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)

    return unique


def open_video(path: str | Path) -> tuple[cv2.VideoCapture | None, int, int, float, int]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        logger.error("Failed to open video: %s", path)
        return None, 0, 0, 0.0, 0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
    fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    logger.info(
        "Opened video %s (%dx%d @ %.2f fps, %d frames)",
        path,
        width,
        height,
        fps,
        total_frames,
    )
    return cap, width, height, fps, total_frames


def resolve_video_sources(video_path: str, video_dir: str) -> list[Path]:
    sources = discover_videos(video_path, video_dir)
    if sources:
        logger.info("Discovered %d CCTV file(s)", len(sources))
        for src in sources:
            logger.info("  - %s", src)
    return sources
