"""Скрипт для ожидания готовности базы данных."""
import logging
import sys
import time
from sqlalchemy import create_engine, text
from app.config import config
from app.utils.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

logger.info("Waiting for database to be ready...")

for i in range(30):
    try:
        engine = create_engine(config.DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database is ready!")
        sys.exit(0)
    except Exception as e:
        if i == 0:
            logger.info(f"Waiting for database... (attempt {i+1}/30)")
        elif i % 5 == 0:
            logger.info(f"Still waiting... (attempt {i+1}/30)")
        else:
            logger.debug(f"Database connection attempt {i+1}/30 failed: {e}")
        time.sleep(1)

logger.error("Database connection timeout!")
sys.exit(1)

