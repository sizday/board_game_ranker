from fastapi import APIRouter

from app.api import ranking, import_table, bgg

router = APIRouter()

router.include_router(ranking.router)
router.include_router(import_table.router)
router.include_router(bgg.router)
