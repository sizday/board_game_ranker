import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.db import get_db
from app.infrastructure.repositories import replace_all_from_table
from app.services.translation import translate_game_descriptions_background

logger = logging.getLogger(__name__)

router = APIRouter()


class ImportTableRequest(BaseModel):
    rows: List[dict]
    # Если True — принудительно обновляем данные всех игр из BGG,
    # иначе обновляем только те, у которых данные старше месяца.
    is_forced_update: bool = False


class ImportTableResponse(BaseModel):
    status: str
    games_imported: int = 0
    message: str = ""


@router.post("/import-table", response_model=ImportTableResponse)
async def import_table(
    request: ImportTableRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Import games data from table to database."""
    logger.info(f"Import table request: {len(request.rows)} rows, forced_update={request.is_forced_update}")
    try:
        replace_all_from_table(
            db,
            request.rows,
            is_forced_update=request.is_forced_update,
        )
        db.commit()
        logger.info(f"Successfully imported {len(request.rows)} games")

        # Запускаем фоновый перевод описаний для игр, у которых его нет
        logger.info("🎯 Scheduling background translation task for imported games")
        background_tasks.add_task(translate_game_descriptions_background, db)

        return ImportTableResponse(
            status="ok",
            games_imported=len(request.rows),
            message="Импорт завершен. Перевод описаний запущен в фоне."
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error(f"Error importing table data: {exc}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(exc))



