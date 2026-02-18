"""
Скрипт для проверки наличия таблиц в БД и их автоматического восстановления при необходимости.
"""
import logging
import sys
from sqlalchemy import text, inspect

from app.infrastructure.db import engine, Base
from app.infrastructure import models  # noqa: F401 - импортируем для регистрации моделей
from app.utils.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def check_and_restore_tables() -> bool:
    """
    Проверяет наличие всех необходимых таблиц в БД.
    Если таблицы отсутствуют, автоматически восстанавливает их.
    
    :return: True если таблицы были восстановлены, False если всё уже было на месте
    """
    required_tables = ["games", "ratings", "ranking_sessions"]
    
    logger.info("Checking database tables...")
    
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        logger.debug(f"Existing tables: {existing_tables}")
    except Exception as e:
        logger.warning(f"Could not inspect database: {e}")
        logger.info("Attempting to restore tables anyway...")
        existing_tables = set()
    
    missing_tables = [tbl for tbl in required_tables if tbl not in existing_tables]
    
    if not missing_tables:
        logger.info("✓ All required tables exist.")
        return False
    
    logger.warning(f"⚠ Missing tables: {', '.join(missing_tables)}")
    logger.info("Restoring tables...")
    
    try:
        # Восстанавливаем все таблицы
        Base.metadata.create_all(bind=engine, checkfirst=True)
        
        # Проверяем результат
        inspector = inspect(engine)
        existing_tables_after = set(inspector.get_table_names())
        
        still_missing = [tbl for tbl in required_tables if tbl not in existing_tables_after]
        
        if still_missing:
            logger.error(f"✗ ERROR: Failed to create tables: {', '.join(still_missing)}")
            return False
        
        logger.info("✓ Tables restored successfully!")
        
        # Помечаем миграции Alembic как применённые, чтобы избежать конфликтов
        if "alembic_version" not in existing_tables_after:
            try:
                import subprocess
                result = subprocess.run(
                    ["alembic", "-c", "alembic.ini", "stamp", "head"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    logger.info("✓ Alembic migrations stamped as applied.")
                else:
                    logger.warning(f"Could not stamp Alembic migrations: {result.stderr}")
            except Exception as e:
                logger.warning(f"Could not stamp Alembic migrations: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ ERROR: Failed to restore tables: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        restored = check_and_restore_tables()
        sys.exit(0 if restored else 0)  # Всё ок в любом случае
    except Exception as e:
        logger.error(f"Table check failed: {e}", exc_info=True)
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

