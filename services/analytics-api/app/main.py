import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.consumers.tracking_consumer import is_consumer_running, start_consumer, stop_consumer
from app.database import SessionLocal, get_db, init_db
from app.domain.anomaly_detector import AnomalyDetector
from app.domain.metrics_aggregator import MetricsAggregator
from app.domain.metrics_service import MetricsService
from app.domain.session_engine import SessionEngine
from app.schemas import FunnelResponse, HealthResponse, MetricsResponse, ReadyResponse

logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import time

    from app.consumers.tracking_consumer import messages_processed

    init_db()
    start_consumer()

    for _ in range(30):
        time.sleep(1)
        if messages_processed() > 100:
            break

    db = SessionLocal()
    try:
        engine = SessionEngine(db)
        engine.close_expired_sessions()
        engine.correlate_pos_transactions()
        AnomalyDetector(db).run_hourly_checks()
        AnomalyDetector(db).detect_loitering()
        MetricsAggregator(db).refresh()
        db.commit()
    finally:
        db.close()
    yield
    stop_consumer()
    db = SessionLocal()
    try:
        engine = SessionEngine(db)
        engine.close_expired_sessions()
        engine.correlate_pos_transactions()
        AnomalyDetector(db).run_hourly_checks()
        AnomalyDetector(db).detect_loitering()
        MetricsAggregator(db).refresh()
        db.commit()
    finally:
        db.close()


app = FastAPI(
    title="Purplle Store Intelligence API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/ready", response_model=ReadyResponse)
def ready() -> ReadyResponse:
    db_status = "ok"
    try:
        from sqlalchemy import text

        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_status = "error"

    return ReadyResponse(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        kafka="ok",
        consumer_running=is_consumer_running(),
    )
