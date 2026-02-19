print("🔄 ROUTES.PY STARTING", flush=True)
import logging

from fastapi import APIRouter

print("📦 IMPORTING API MODULES", flush=True)
from app.api import import_table, clear_database, bgg, games
# from app.api import ranking  # Temporarily disabled - may have import issues
print("✅ API MODULES IMPORTED", flush=True)

logger = logging.getLogger(__name__)

router = APIRouter()
print("🔧 API ROUTER CREATED", flush=True)
logger.info("API router created")

# router.include_router(ranking.router)  # Temporarily disabled
# logger.info("Ranking router included")
router.include_router(import_table.router)
logger.info("Import table router included")
router.include_router(clear_database.router)
logger.info("Clear database router included")
router.include_router(bgg.router)
logger.info("BGG router included")
router.include_router(games.router)
logger.info("Games router included")

logger.debug("API routes registered")
