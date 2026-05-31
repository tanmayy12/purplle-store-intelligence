from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    store_id: str = "ST1008"
    store_name: str = "Brigade_Bangalore"
    operating_date: str = "2026-04-10"
    database_url: str = "postgresql://store:CHANGE_ME_STRONG_PASSWORD@postgres:5432/store_intelligence"
    kafka_bootstrap: str = "redpanda:9092"
    kafka_group_id: str = "analytics-api"
    kafka_topic_raw: str = "store.tracking.raw"
    kafka_topic_anomalies: str = "store.anomalies"
    kafka_topic_session: str = "store.tracking.session"
    kafka_topic_dlq: str = "store.tracking.dlq"
    zones_config_path: str = "/config/zones/zones.yaml"
    pos_csv_path: str = "/data/seed/ground_truth_pos.csv"
    session_timeout_sec: int = 1800
    reentry_cooldown_sec: int = 120
    bounce_threshold_sec: int = 30
    engaged_min_sec: int = 60
    checkout_min_sec: int = 15
    pos_match_window_before_sec: int = 600
    pos_match_window_after_sec: int = 120
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    kafka_retry_max_attempts: int = 5
    kafka_retry_initial_delay_sec: int = 1
    kafka_retry_max_delay_sec: int = 30

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        # Check for placeholder password
        if "CHANGE_ME_STRONG_PASSWORD" in self.database_url:
            errors.append("DATABASE_URL contains placeholder password CHANGE_ME_STRONG_PASSWORD. Please set a strong password.")
        
        # Check operating date format
        try:
            from datetime import datetime
            datetime.fromisoformat(self.operating_date)
        except ValueError:
            errors.append(f"OPERATING_DATE '{self.operating_date}' is not a valid ISO date (YYYY-MM-DD).")
        
        # Check positive numeric values
        if self.session_timeout_sec <= 0:
            errors.append("SESSION_TIMEOUT_SEC must be positive.")
        if self.reentry_cooldown_sec < 0:
            errors.append("REENTRY_COOLDOWN_SEC must be non-negative.")
        if self.kafka_retry_max_attempts <= 0:
            errors.append("KAFKA_RETRY_MAX_ATTEMPTS must be positive.")
        
        # Check CORS origins
        if not self.cors_origins:
            errors.append("CORS_ORIGINS cannot be empty.")
        
        return errors


settings = Settings()
config_errors = settings.validate()
if config_errors:
    import sys
    import logging
    logging.basicConfig(level=logging.ERROR)
    logger = logging.getLogger(__name__)
    logger.error("Configuration validation failed:")
    for error in config_errors:
        logger.error(f"  - {error}")
    logger.error("Please fix these errors in your .env file before starting the application.")
    sys.exit(1)
