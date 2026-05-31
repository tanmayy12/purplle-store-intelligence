import os
from dataclasses import dataclass


@dataclass
class Settings:
    store_id: str = os.getenv("STORE_ID", "ST1008")
    operating_date: str = os.getenv("OPERATING_DATE", "2026-04-10")
    kafka_bootstrap: str = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
    kafka_topic_raw: str = os.getenv("KAFKA_TOPIC_RAW", "store.tracking.raw")
    zones_config_path: str = os.getenv("ZONES_CONFIG_PATH", "/config/zones/zones.yaml")
    pos_csv_path: str = os.getenv("POS_CSV_PATH", "/data/seed/ground_truth_pos.csv")
    video_path: str = os.getenv("VIDEO_PATH", "")
    video_dir: str = os.getenv(
        "VIDEO_DIR",
        "/data/cctv",
    )
    yolo_model: str = os.getenv("YOLO_MODEL", "yolov8n.pt")
    frame_skip: int = int(os.getenv("FRAME_SKIP", "2"))
    simulation_mode: str = os.getenv("SIMULATION_MODE", "auto")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    reentry_cooldown_sec: int = int(os.getenv("REENTRY_COOLDOWN_SEC", "120"))
    detection_confidence_threshold: float = float(os.getenv("DETECTION_CONFIDENCE_THRESHOLD", "0.3"))
    staff_zone_dwell_threshold_frames: int = int(os.getenv("STAFF_ZONE_DWELL_THRESHOLD_FRAMES", "30"))
    track_loss_timeout_sec: int = int(os.getenv("TRACK_LOSS_TIMEOUT_SEC", "5"))


settings = Settings()
