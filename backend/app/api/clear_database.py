import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.db import get_db
from app.infrastructure.repositories import clear_all_data

logger = logging.getLogger(__name__)

router = APIRouter()


class ClearDatabaseRequest(BaseModel):
    confirm: bool = False  # Требуем явного подтверждения


class ClearDatabaseResponse(BaseModel):
    status: str
    games_deleted: int = 0
    ratings_deleted: int = 0
    sessions_deleted: int = 0
    users_deleted: int = 0
    message: str = ""


@router.post("/clear-database", response_model=ClearDatabaseResponse)
async def clear_database(
    request: ClearDatabaseRequest,
    db: Session = Depends(get_db)
):
    """Clear all data from database (games, ratings, ranking sessions)."""
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Для очистки базы данных требуется явное подтверждение. Установите confirm=true."
        )

    logger.info("Clear database request confirmed")
    try:
        result = clear_all_data(db)
        db.commit()
        logger.info(f"Successfully cleared database: {result}")

        return ClearDatabaseResponse(
            status="ok",
            games_deleted=result["games_deleted"],
            ratings_deleted=result["ratings_deleted"],
            sessions_deleted=result["sessions_deleted"],
            users_deleted=result["users_deleted"],
            message="База данных успешно очищена."
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error(f"Error clearing database: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))