from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.domain.models import FirstTier, Game, RankingRequest, SecondTier
from app.domain.services import rank_games
from app.infrastructure.db import get_db
from app.services.ranking import RankingService

router = APIRouter()


class GameItem(BaseModel):
    id: int
    name: str


class RankGamesRequest(BaseModel):
    games: List[GameItem]
    top_n: int = 50


class RankGamesResponse(BaseModel):
    ranked_games: List[GameItem]


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
    next_game: GameItem | None = None
    top: List[GameItem] | None = None
    message: str = ""


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
            game=GameItem(id=data["game"]["id"], name=data["game"]["name"]),
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/ranking/answer-first", response_model=RankingAnswerResponse)
async def ranking_answer_first(
    request: RankingAnswerRequest, db: Session = Depends(get_db)
):
    """User answer for first tier ranking (bad/good/excellent)."""
    if request.session_id is None or request.game_id is None or request.tier is None:
        raise HTTPException(
            status_code=400, detail="session_id, game_id и tier обязательны"
        )

    try:
        tier = FirstTier(request.tier)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Некорректное значение tier: {request.tier}"
        )

    service = RankingService(db)
    try:
        data = service.answer_first_tier(
            session_id=request.session_id,
            game_id=request.game_id,
            tier=tier,
        )
        db.commit()

        # Build response
        response_data: dict = {"phase": data.get("phase")}

        if data.get("phase") in ["first_tier", "second_tier"] and "next_game" in data:
            response_data["next_game"] = GameItem(
                id=data["next_game"]["id"],
                name=data["next_game"]["name"],
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
async def ranking_answer_second(
    request: RankingAnswerRequest, db: Session = Depends(get_db)
):
    """User answer for second tier ranking (super_cool/cool/excellent)."""
    if request.session_id is None or request.game_id is None or request.tier is None:
        raise HTTPException(
            status_code=400, detail="session_id, game_id и tier обязательны"
        )

    try:
        tier = SecondTier(request.tier)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Некорректное значение tier: {request.tier}"
        )

    service = RankingService(db)
    try:
        data = service.answer_second_tier(
            session_id=request.session_id,
            game_id=request.game_id,
            tier=tier,
        )
        db.commit()

        # Build response
        response_data: dict = {"phase": data.get("phase")}

        if data.get("phase") in ["first_tier", "second_tier"] and "next_game" in data:
            response_data["next_game"] = GameItem(
                id=data["next_game"]["id"],
                name=data["next_game"]["name"],
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



