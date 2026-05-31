from __future__ import annotations

import logging
import os
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO

logger = logging.getLogger(__name__)


def _resolve_tracker(tracker: str) -> str:
    if tracker != "bytetrack.yaml":
        return tracker
    for candidate in ("/app/bytetrack.yaml", "bytetrack.yaml"):
        if os.path.isfile(candidate):
            return candidate
    return tracker


class PersonDetector:
    """YOLOv8n person detection with ByteTrack multi-object tracking."""

    def __init__(self, model_path: str = "yolov8n.pt", tracker: str = "bytetrack.yaml"):
        self.model = YOLO(model_path)
        self.tracker = _resolve_tracker(tracker)
        logger.info("Loaded YOLOv8n model=%s tracker=%s", model_path, self.tracker)

    def track_frame(
        self,
        frame: np.ndarray,
        frame_width: int,
        frame_height: int,
    ) -> list[dict[str, Any]]:
        results = self.model.track(
            frame,
            persist=True,
            classes=[0],
            tracker=self.tracker,
            verbose=False,
            conf=0.35,
            iou=0.5,
        )

        tracks: list[dict[str, Any]] = []
        if not results or results[0].boxes is None:
            return tracks

        boxes = results[0].boxes
        for i in range(len(boxes)):
            xyxy = boxes.xyxy[i].cpu().numpy()
            track_id = int(boxes.id[i].cpu().numpy()) if boxes.id is not None else i + 1
            confidence = float(boxes.conf[i].cpu().numpy())
            x1, y1, x2, y2 = map(float, xyxy)

            # Foot point (bottom-centre) improves zone mapping for overhead CCTV
            foot_x = ((x1 + x2) / 2.0) / frame_width
            foot_y = y2 / frame_height
            cx = foot_x
            cy = foot_y

            tracks.append(
                {
                    "track_id": track_id,
                    "person_id": str(track_id),
                    "bbox": [x1, y1, x2, y2],
                    "centroid": (cx, cy),
                    "foot_point": (foot_x, foot_y),
                    "confidence": confidence,
                }
            )
        return tracks

    def reset_tracker(self) -> None:
        """Reset tracker state between videos."""
        self.model.predictor = None  # type: ignore[attr-defined]
        logger.debug("ByteTrack state reset")
