import logging
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.db import get_db
from app.infrastructure.repositories import get_or_create_user, get_user_games_with_bgg_links

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateUserRequest(BaseModel):
    telegram_id: int
    name: str


class UserResponse(BaseModel):
    id: str
    name: str
    telegram_id: int


class UserGamesResponse(BaseModel):
    games: List[Dict[str, Any]]


@router.post("/users", response_model=UserResponse)
async def create_or_update_user(
    request: CreateUserRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    """
    Создает нового пользователя или обновляет существующего.

    Если пользователь с таким telegram_id уже существует,
    обновляет его имя.
    """
    logger.info(f"Creating/updating user: telegram_id={request.telegram_id}, name='{request.name}'")

    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="Имя пользователя не может быть пустым")

    if len(request.name.strip()) > 100:
        raise HTTPException(status_code=400, detail="Имя пользователя слишком длинное (максимум 100 символов)")

    try:
        user = get_or_create_user(
            session=db,
            telegram_id=request.telegram_id,
            name=request.name.strip()
        )

        db.commit()

        return UserResponse(
            id=str(user.id),
            name=user.name,
            telegram_id=user.telegram_id
        )

    except Exception as exc:
        db.rollback()
        logger.error(f"Error creating/updating user: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка при создании пользователя: {exc}")


@router.get("/users/{telegram_id}/games", response_model=UserGamesResponse)
async def get_user_games(
    telegram_id: int,
    db: Session = Depends(get_db),
) -> UserGamesResponse:
    """
    Получает список игр пользователя с ссылками на BGG.

    Возвращает только игры с BGG ID, отсортированные лексикографически.
    """
    logger.info(f"Getting games for user with telegram_id: {telegram_id}")

    try:
        # Находим пользователя по telegram_id
        from app.infrastructure.models import UserModel
        user = db.query(UserModel).filter(UserModel.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        games = get_user_games_with_bgg_links(db, str(user.id))

        return UserGamesResponse(games=games)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error getting user games: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка при получении списка игр: {exc}")