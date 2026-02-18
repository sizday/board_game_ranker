import logging
from typing import List

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infrastructure.db import get_db
from app.infrastructure.models import GameModel
from app.infrastructure.repositories import save_game_from_bgg_data
from app.services.translation import translate_game_descriptions_background

logger = logging.getLogger(__name__)

router = APIRouter()


class GameDetails(BaseModel):
    id: int
    name: str
    bgg_id: int | None = None
    bgg_rank: int | None = None
    niza_games_rank: int | None = None
    yearpublished: int | None = None
    bayesaverage: float | None = None
    usersrated: int | None = None
    minplayers: int | None = None
    maxplayers: int | None = None
    playingtime: int | None = None
    minplaytime: int | None = None
    maxplaytime: int | None = None
    minage: int | None = None
    average: float | None = None
    numcomments: int | None = None
    owned: int | None = None
    trading: int | None = None
    wanting: int | None = None
    wishing: int | None = None
    averageweight: float | None = None
    numweights: int | None = None
    categories: list[str] | None = None
    mechanics: list[str] | None = None
    designers: list[str] | None = None
    publishers: list[str] | None = None
    image: str | None = None
    thumbnail: str | None = None
    description: str | None = None
    description_ru: str | None = None


class GamesSearchResponse(BaseModel):
    games: List[GameDetails]


@router.get("/games/search", response_model=GamesSearchResponse)
async def search_games_in_db(
    name: str,
    exact: bool = False,
    limit: int = 5,
    db: Session = Depends(get_db)
) -> GamesSearchResponse:
    """
    Поиск игр в базе данных по названию.

    :param name: Название игры для поиска
    :param exact: Если True, ищет только точные совпадения
    :param limit: Максимальное количество результатов
    :param db: Сессия базы данных
    """
    logger.info(f"Database search request: name='{name}', exact={exact}, limit={limit}")

    # Формируем запрос к базе данных
    query = db.query(GameModel)

    if exact:
        # Точное совпадение
        query = query.filter(func.lower(GameModel.name) == func.lower(name))
    else:
        # Неточное совпадение - ищем по подстроке
        query = query.filter(GameModel.name.ilike(f"%{name}%"))

    # Ограничиваем количество результатов
    query = query.limit(limit)

    games_db = query.all()

    logger.info(f"Database search found {len(games_db)} games for query: '{name}'")

    games = []
    for gm in games_db:
        games.append(GameDetails(
            id=gm.id,
            name=gm.name,
            bgg_id=gm.bgg_id,
            bgg_rank=gm.bgg_rank,
            niza_games_rank=gm.niza_games_rank,
            yearpublished=gm.yearpublished,
            bayesaverage=gm.bayesaverage,
            usersrated=gm.usersrated,
            minplayers=gm.minplayers,
            maxplayers=gm.maxplayers,
            playingtime=gm.playingtime,
            minplaytime=gm.minplaytime,
            maxplaytime=gm.maxplaytime,
            minage=gm.minage,
            average=gm.average,
            numcomments=gm.numcomments,
            owned=gm.owned,
            trading=gm.trading,
            wanting=gm.wanting,
            wishing=gm.wishing,
            averageweight=gm.averageweight,
            numweights=gm.numweights,
            categories=gm.categories,
            mechanics=gm.mechanics,
            designers=gm.designers,
            publishers=gm.publishers,
            image=gm.image,
            thumbnail=gm.thumbnail,
            description=gm.description,
        ))

    return GamesSearchResponse(games=games)


@router.post("/games/save-from-bgg", response_model=GameDetails)
async def save_game_from_bgg(
    bgg_data: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> GameDetails:
    """
    Сохраняет игру в базу данных на основе данных из BGG API.

    :param bgg_data: Данные игры из BGG API
    :param background_tasks: FastAPI BackgroundTasks для фонового перевода
    :param db: Сессия базы данных
    :return: Сохраненная игра
    """
    game_name = bgg_data.get('name', 'Unknown')
    game_id = bgg_data.get('id')
    logger.info(f"💾 Saving game from BGG data: '{game_name}' (BGG ID: {game_id})")

    try:
        game = save_game_from_bgg_data(db, bgg_data)
        db.commit()

        logger.info(f"✅ Game saved successfully: '{game_name}' (DB ID: {game.id})")

        # Запускаем фоновый перевод описания, если оно есть
        if game.description and not game.description_ru:
            logger.info(f"🎯 Scheduling translation for game: '{game_name}' (has description, no Russian translation)")
            background_tasks.add_task(translate_game_descriptions_background, db)
        elif not game.description:
            logger.debug(f"ℹ️  Game '{game_name}' has no description to translate")
        else:
            logger.debug(f"ℹ️  Game '{game_name}' already has Russian translation")

        return GameDetails(
            id=game.id,
            name=game.name,
            bgg_id=game.bgg_id,
            bgg_rank=game.bgg_rank,
            niza_games_rank=game.niza_games_rank,
            yearpublished=game.yearpublished,
            bayesaverage=game.bayesaverage,
            usersrated=game.usersrated,
            minplayers=game.minplayers,
            maxplayers=game.maxplayers,
            playingtime=game.playingtime,
            minplaytime=game.minplaytime,
            maxplaytime=game.maxplaytime,
            minage=game.minage,
            average=game.average,
            numcomments=game.numcomments,
            owned=game.owned,
            trading=game.trading,
            wanting=game.wanting,
            wishing=game.wishing,
            averageweight=game.averageweight,
            numweights=game.numweights,
            categories=game.categories,
            mechanics=game.mechanics,
            designers=game.designers,
            publishers=game.publishers,
            image=game.image,
            thumbnail=game.thumbnail,
            description=game.description,
            description_ru=game.description_ru,
        )

    except Exception as exc:
        db.rollback()
        logger.error(f"❌ Error saving game '{game_name}' from BGG data: {exc}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(exc))