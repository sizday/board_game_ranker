from sqlalchemy import JSON, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .db import Base
from app.domain.models import GameGenre


class UserModel(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=func.gen_random_uuid(), index=True)
    name = Column(String, nullable=False)
    telegram_id = Column(Integer, nullable=False, unique=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    ratings = relationship("RatingModel", back_populates="user", cascade="all, delete-orphan")
    ranking_sessions = relationship("RankingSessionModel", back_populates="user", cascade="all, delete-orphan")


class GameModel(Base):
    __tablename__ = "games"

    id = Column(UUID(as_uuid=True), primary_key=True, default=func.gen_random_uuid(), index=True)
    name = Column(String, nullable=False)
    # ID игры на BGG (для последующего обновления по API)
    bgg_id = Column(Integer, nullable=True, index=True)
    bgg_rank = Column(Integer, nullable=True)
    niza_games_rank = Column(Integer, nullable=True)
    # Ограничиваем жанр только перечисленными значениями через PostgreSQL ENUM
    genre = Column(
        Enum(GameGenre),
        nullable=True,
    )
    # Статистика и доп. метаданные из BGG
    yearpublished = Column(Integer, nullable=True)
    bayesaverage = Column(Float, nullable=True)
    usersrated = Column(Integer, nullable=True)
    # Параметры игры
    minplayers = Column(Integer, nullable=True)
    maxplayers = Column(Integer, nullable=True)
    playingtime = Column(Integer, nullable=True)
    minplaytime = Column(Integer, nullable=True)
    maxplaytime = Column(Integer, nullable=True)
    minage = Column(Integer, nullable=True)
    # Статистика BGG
    average = Column(Float, nullable=True)
    numcomments = Column(Integer, nullable=True)
    owned = Column(Integer, nullable=True)
    trading = Column(Integer, nullable=True)
    wanting = Column(Integer, nullable=True)
    wishing = Column(Integer, nullable=True)
    averageweight = Column(Float, nullable=True)
    numweights = Column(Integer, nullable=True)
    # Списки (из link-ов BGG)
    categories = Column(JSON, nullable=True)
    mechanics = Column(JSON, nullable=True)
    designers = Column(JSON, nullable=True)
    publishers = Column(JSON, nullable=True)
    image = Column(String, nullable=True)
    thumbnail = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    description_ru = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    ratings = relationship("RatingModel", back_populates="game", cascade="all, delete-orphan")


class RatingModel(Base):
    __tablename__ = "ratings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=func.gen_random_uuid(), index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    game_id = Column(UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    rank = Column(Integer, nullable=False)

    user = relationship("UserModel", back_populates="ratings")
    game = relationship("GameModel", back_populates="ratings")


class RankingSessionModel(Base):
    """
    Сессия ранжирования для одного пользователя.

    Для простоты состояние храним в JSON-полях.
    """

    __tablename__ = "ranking_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=func.gen_random_uuid(), index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

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

    user = relationship("UserModel", back_populates="ranking_sessions")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
