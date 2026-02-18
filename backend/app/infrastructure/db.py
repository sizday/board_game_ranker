import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import config

logger = logging.getLogger(__name__)

DATABASE_URL = config.DATABASE_URL

logger.info(f"Initializing database connection: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else '***'}")
engine = create_engine(DATABASE_URL, echo=config.DEBUG, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


def get_db():
    """Database dependency for FastAPI."""
    db = SessionLocal()
    try:
        logger.debug("Database session created")
        yield db
    finally:
        db.close()
        logger.debug("Database session closed")


def init_db() -> None:
    """Создает таблицы в БД, если их еще нет."""
    logger.info("Initializing database tables...")
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine, checkfirst=True)
    logger.info("Database tables initialized")


