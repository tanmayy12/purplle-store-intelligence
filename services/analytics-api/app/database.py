import logging
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.base import Base

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    alembic_ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini))
    
    # Check if alembic version table exists
    inspector = inspect(engine)
    
    if "alembic_version" not in inspector.get_table_names():
        logger.info("No alembic version table found, running migrations from scratch")
        # Don't stamp - let upgrade handle it from the beginning
    else:
        logger.info("Alembic version table found, running migrations")
    
    command.upgrade(alembic_cfg, "head")
    logger.info("Alembic migrations applied")


def init_db() -> None:
    run_migrations()
