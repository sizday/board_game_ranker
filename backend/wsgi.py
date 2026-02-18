from fastapi import FastAPI
from uvicorn import run

from app.api.routes import router as api_router
from app.infrastructure.db import init_db
from app.config import config
from app.utils.logging import setup_logging, get_logger

# Настройка логирования
setup_logging()

logger = get_logger(__name__)

app = FastAPI(
    title="Board Game Ranker API",
    description="API for ranking board games",
    version="1.0.0",
)

logger.info("FastAPI application created")

# Initialize database (создаёт таблицы, если их нет)
# Миграции Alembic уже применены в start.sh, так что это просто подстраховка
try:
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialization completed successfully")
except Exception as e:
    # Если таблицы уже созданы через миграции, это нормально
    logger.warning(f"Database initialization note: {e}")

# Include API router
app.include_router(api_router, prefix="/api")
logger.info("API router included")


@app.get("/health")
async def health_check():
    logger.debug("Health check requested")
    return {"status": "ok"}


if __name__ == "__main__":
    logger.info(f"Starting server on {config.HOST}:{config.PORT}")
    run(app, host=config.HOST, port=config.PORT)


