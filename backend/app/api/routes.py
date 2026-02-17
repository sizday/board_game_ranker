from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.domain.models import FirstTier, Game, RankingRequest, SecondTier
from app.domain.services import rank_games
from app.infrastructure.db import SessionLocal, get_db
from app.infrastructure.repositories import replace_all_from_table
from app.services.ranking import RankingService
from app.services.bgg import search_boardgame, get_boardgame_details

router = APIRouter()


# Pydantic models for request/response
from pydantic import BaseModel


class GameItem(BaseModel):
    id: int
    name: str


class RankGamesRequest(BaseModel):
    games: List[GameItem]
    top_n: int = 50


class RankGamesResponse(BaseModel):
    ranked_games: List[GameItem]


class ImportTableRequest(BaseModel):
    rows: List[dict]


class ImportTableResponse(BaseModel):
    status: str
    games_imported: int = 0
    message: str = ""


class RankingStartRequest(BaseModel):
    user_name: str


class RankingStartResponse(BaseModel):
    session_id: int
    game: GameItem


class RankingAnswerRequest(BaseModel):
    session_id: int
    game_id: int
    tier: str


class RankingAnswerResponse(BaseModel):
    phase: str
    next_game: GameItem = None
    top: List[GameItem] = None
    message: str = ""


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


@router.post("/rank", response_model=RankGamesResponse)
async def rank_games_endpoint(request: RankGamesRequest):
    """Rank games based on provided list."""
    games = [Game(id=item.id, name=item.name) for item in request.games]
    ranking_request = RankingRequest(games=games, top_n=request.top_n)

    result = rank_games(ranking_request)

    return RankGamesResponse(
        ranked_games=[
            GameItem(id=rg.game.id, name=rg.game.name)
            for rg in result.ranked_games
        ]
    )


@router.post("/import-table", response_model=ImportTableResponse)
async def import_table(request: ImportTableRequest, db: Session = Depends(get_db)):
    """Import games data from table to database."""
    try:
        replace_all_from_table(db, request.rows)
        db.commit()
        return ImportTableResponse(
            status="ok",
            games_imported=len(request.rows)
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/ranking/start", response_model=RankingStartResponse)
async def ranking_start(request: RankingStartRequest, db: Session = Depends(get_db)):
    """Start a ranking session for a user."""
    if not request.user_name:
        raise HTTPException(status_code=400, detail="user_name is required")

    service = RankingService(db)
    try:
        data = service.start_session(user_name=request.user_name)
        db.commit()
        return RankingStartResponse(
            session_id=data["session_id"],
            game=GameItem(id=data["game"]["id"], name=data["game"]["name"])
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/ranking/answer-first", response_model=RankingAnswerResponse)
async def ranking_answer_first(request: RankingAnswerRequest, db: Session = Depends(get_db)):
    """User answer for first tier ranking (bad/good/excellent)."""
    if request.session_id is None or request.game_id is None or request.tier is None:
        raise HTTPException(status_code=400, detail="session_id, game_id и tier обязательны")

    try:
        tier = FirstTier(request.tier)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Некорректное значение tier: {request.tier}")

    service = RankingService(db)
    try:
        data = service.answer_first_tier(
            session_id=request.session_id,
            game_id=request.game_id,
            tier=tier,
        )
        db.commit()

        # Build response
        response_data = {"phase": data.get("phase")}

        if data.get("phase") in ["first_tier", "second_tier"] and "next_game" in data:
            response_data["next_game"] = GameItem(
                id=data["next_game"]["id"],
                name=data["next_game"]["name"]
            )

        if data.get("phase") == "final" and "top" in data:
            response_data["top"] = [
                GameItem(id=item["id"], name=item["name"])
                for item in data["top"]
            ]

        if data.get("phase") == "completed" and "message" in data:
            response_data["message"] = data["message"]

        return RankingAnswerResponse(**response_data)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/ranking/answer-second", response_model=RankingAnswerResponse)
async def ranking_answer_second(request: RankingAnswerRequest, db: Session = Depends(get_db)):
    """User answer for second tier ranking (super_cool/cool/excellent)."""
    if request.session_id is None or request.game_id is None or request.tier is None:
        raise HTTPException(status_code=400, detail="session_id, game_id и tier обязательны")

    try:
        tier = SecondTier(request.tier)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Некорректное значение tier: {request.tier}")

    service = RankingService(db)
    try:
        data = service.answer_second_tier(
            session_id=request.session_id,
            game_id=request.game_id,
            tier=tier,
        )
        db.commit()

        # Build response
        response_data = {"phase": data.get("phase")}

        if data.get("phase") in ["first_tier", "second_tier"] and "next_game" in data:
            response_data["next_game"] = GameItem(
                id=data["next_game"]["id"],
                name=data["next_game"]["name"]
            )

        if data.get("phase") == "final" and "top" in data:
            response_data["top"] = [
                GameItem(id=item["id"], name=item["name"])
                for item in data["top"]
            ]

        if data.get("phase") == "completed" and "message" in data:
            response_data["message"] = data["message"]

        return RankingAnswerResponse(**response_data)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


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

        # Для каждого найденного ID забираем подробности
        games: List[BGGGameDetails] = []
        for item in found:
            details = get_boardgame_details(item["id"])
            games.append(BGGGameDetails(**details))

        return BGGSearchResponse(games=games)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Ошибка при обращении к BGG: {exc}")
