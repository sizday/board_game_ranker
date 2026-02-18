"""
Скрипт для полного восстановления таблиц в БД.

Использование:
    python reset_db.py          # Пересоздать все таблицы
    python reset_db.py --force  # Принудительно удалить и пересоздать
"""
import logging
import sys
from sqlalchemy import text

from app.infrastructure.db import engine, Base
from app.infrastructure import models  # noqa: F401 - импортируем для регистрации моделей
from app.utils.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def reset_database(force: bool = False) -> None:
    """
    Восстанавливает все таблицы в БД.
    
    :param force: Если True, сначала удаляет все таблицы, затем создаёт заново.
    """
    logger.info("=== Database Reset ===")
    
    with engine.connect() as conn:
        if force:
            logger.info("Dropping all tables...")
            # Удаляем все таблицы в правильном порядке (с учётом foreign keys)
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS ratings CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS ranking_sessions CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS games CASCADE"))
            # Удаляем типы ENUM, если они есть
            conn.execute(text("DROP TYPE IF EXISTS gamegenre CASCADE"))
            conn.commit()
            logger.info("All tables dropped.")
        
        logger.info("Creating all tables...")
        # Создаём все таблицы заново
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("Tables created successfully!")
        
        # Проверяем, какие таблицы созданы
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """))
        tables = [row[0] for row in result]
        logger.info(f"Created tables: {', '.join(tables)}")
        
        # Применяем миграции Alembic (если нужно)
        logger.info("Applying Alembic migrations...")
        import subprocess
        result = subprocess.run(
            ["alembic", "-c", "alembic.ini", "stamp", "head"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logger.info("Alembic migrations stamped as applied.")
        else:
            logger.warning(f"Could not stamp Alembic migrations: {result.stderr}")
    
    logger.info("=== Database reset complete! ===")


if __name__ == "__main__":
    force = "--force" in sys.argv or "-f" in sys.argv
    try:
        reset_database(force=force)
    except Exception as e:
        logger.error(f"Database reset failed: {e}", exc_info=True)
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

