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
    created: bool = False
    name_updated: bool = False


class UserGamesResponse(BaseModel):
    games: List[Dict[str, Any]]


@router.post("/users", response_model=UserResponse, tags=["users"])
async def create_or_update_user(
    request: CreateUserRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    """
    Create a new user or update an existing one.

    If a user with the given telegram_id already exists,
    their name will be updated.
    """
    logger.info(f"Creating/updating user: telegram_id={request.telegram_id}, name='{request.name}'")

    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="User name cannot be empty")

    if len(request.name.strip()) > 100:
        raise HTTPException(status_code=400, detail="User name is too long (maximum 100 characters)")

    try:
        user, created, name_updated = get_or_create_user(
            session=db,
            telegram_id=request.telegram_id,
            name=request.name.strip()
        )

        db.commit()

        return UserResponse(
            id=str(user.id),
            name=user.name,
            telegram_id=user.telegram_id,
            created=created,
            name_updated=name_updated
        )

    except Exception as exc:
        db.rollback()
        logger.error(f"Error creating/updating user: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating user: {exc}")


@router.get("/users/{telegram_id}/games", response_model=UserGamesResponse, tags=["users"])
async def get_user_games(
    telegram_id: int,
    db: Session = Depends(get_db),
) -> UserGamesResponse:
    """
    Get a list of user's games with BGG links.

    Returns only games that have a BGG ID, sorted alphabetically.
    """
    logger.info(f"Getting games for user with telegram_id: {telegram_id}")

    try:
        # Находим пользователя по telegram_id
        from app.infrastructure.models import UserModel
        user = db.query(UserModel).filter(UserModel.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        games = get_user_games_with_bgg_links(db, str(user.id))

        return UserGamesResponse(games=games)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error getting user games: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving user games: {exc}")