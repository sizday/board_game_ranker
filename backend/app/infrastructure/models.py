from sqlalchemy import JSON, Column, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from .db import Base
from app.domain.models import GameGenre


class GameModel(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    bgg_rank = Column(Integer, nullable=True)
    niza_games_rank = Column(Integer, nullable=True)
    # Ограничиваем жанр только перечисленными значениями через PostgreSQL ENUM
    genre = Column(
        Enum(GameGenre),
        nullable=True,
    )

    ratings = relationship("RatingModel", back_populates="game", cascade="all, delete-orphan")


class RatingModel(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String, nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    rank = Column(Integer, nullable=False)

    game = relationship("GameModel", back_populates="ratings")


class RankingSessionModel(Base):
    """
    Сессия ранжирования для одного пользователя.

    Для простоты состояние храним в JSON-полях.
    """

    __tablename__ = "ranking_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String, nullable=False, index=True)

    # first_tier, second_tier, ordering, final
    state = Column(String, nullable=False, default="first_tier")

    # Список id игр, участвующих в ранжировании (в порядке обхода)
    games = Column(JSON, nullable=False)

    # {"game_id": "bad/good/excellent"}
    first_tiers = Column(JSON, nullable=False, default=dict)

    # {"game_id": "super_cool/cool/excellent"}
    second_tiers = Column(JSON, nullable=False, default=dict)

    # Список id игр, отобранных после первого прохода
    candidate_ids = Column(JSON, nullable=True)

    # {"second_tier": [game_id, ...]} — порядок внутри мини-групп
    group_orders = Column(JSON, nullable=True)

    # Финальный порядок топ-50: [game_id, ...]
    final_order = Column(JSON, nullable=True)

    current_index_first = Column(Integer, nullable=False, default=0)
    current_index_second = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
