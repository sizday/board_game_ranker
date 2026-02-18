import logging
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.bgg import search_boardgame, get_boardgame_details

logger = logging.getLogger(__name__)

router = APIRouter()


class BGGGameDetails(BaseModel):
    id: int | None
    name: str | None
    yearpublished: int | None
    rank: int | None
    bayesaverage: float | None
    usersrated: int | None
    image: str | None
    thumbnail: str | None


class BGGSearchResponse(BaseModel):
    games: List[BGGGameDetails]


@router.get("/bgg/search", response_model=BGGSearchResponse)
async def bgg_search(name: str, exact: bool = False) -> BGGSearchResponse:
    """
    Поиск игр на BGG по названию с возвратом подробной информации,
    включая мировой рейтинг и URL изображений.
    """
    logger.info(f"API запрос на поиск игры: name='{name}', exact={exact}")
    try:
        found = search_boardgame(name, exact=exact)
        if not found:
            logger.warning(f"Поиск не дал результатов для запроса: name='{name}', exact={exact}")
            return BGGSearchResponse(games=[])

        logger.info(f"Найдено {len(found)} игр, загружаем детали...")
        games: List[BGGGameDetails] = []
        for idx, item in enumerate(found, 1):
            try:
                game_id = item.get("id")
                if not game_id:
                    logger.warning(f"Пропущен item без id: {item}")
                    continue
                logger.debug(f"Загрузка деталей игры {idx}/{len(found)}: game_id={game_id}")
                details = get_boardgame_details(game_id)
                games.append(BGGGameDetails(**details))
            except Exception as e:
                logger.error(f"Ошибка при загрузке деталей игры game_id={item.get('id')}: {e}", exc_info=True)
                # Продолжаем обработку остальных игр

        logger.info(f"Успешно загружено {len(games)} игр из {len(found)} найденных")
        return BGGSearchResponse(games=games)
    except ValueError as exc:
        logger.error(f"Ошибка конфигурации BGG: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка конфигурации BGG: {exc}")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Ошибка при обращении к BGG API: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Ошибка при обращении к BGG: {exc}")



