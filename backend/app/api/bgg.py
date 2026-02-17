from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.bgg import search_boardgame, get_boardgame_details

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
    try:
        found = search_boardgame(name, exact=exact)
        if not found:
            return BGGSearchResponse(games=[])

        games: List[BGGGameDetails] = []
        for item in found:
            details = get_boardgame_details(item["id"])
            games.append(BGGGameDetails(**details))

        return BGGSearchResponse(games=games)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Ошибка при обращении к BGG: {exc}")



