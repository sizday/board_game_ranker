import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any

from sqlalchemy.orm import Session

from app.config import config
from app.domain.models import GameGenre
from app.services.bgg import get_boardgame_details, search_boardgame
from .models import GameModel, RatingModel

logger = logging.getLogger(__name__)


GAME_UPDATE_DELTA = timedelta(days=config.GAME_UPDATE_DAYS)


def _parse_genre(value: Any) -> GameGenre | None:
    """
    Приводит строковое значение жанра из таблицы к enum GameGenre, если возможно.
    Ожидает либо уже GameGenre, либо строку с value из перечисления.
    """
    if value is None or value == "":
        return None
    if isinstance(value, GameGenre):
        return value
    try:
        return GameGenre(value)
    except ValueError:
        return None


def _should_update_game(game: GameModel, is_forced_update: bool) -> bool:
    """
    Возвращает True, если данные игры нужно обновить запросом к BGG.

    - при is_forced_update=True обновляем всегда;
    - иначе — только если прошло больше месяца с момента последнего обновления
      (updated_at) или updated_at отсутствует.
    """
    if is_forced_update:
        logger.debug(f"Forced update requested for game: {game.name}")
        return True
    if not game.updated_at:
        logger.debug(f"Game {game.name} has no updated_at, update needed")
        return True
    now = datetime.now(timezone.utc)
    should_update = now - game.updated_at > GAME_UPDATE_DELTA
    if should_update:
        logger.debug(f"Game {game.name} data is outdated (last update: {game.updated_at})")
    return should_update


def _fetch_bgg_details_for_row(row: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    Вспомогательная функция: по названию (и, опционально, bgg_id) получает
    подробные данные игры из BGG.

    Приоритет:
    1. Если в строке есть явный bgg_id — сразу дергаем get_boardgame_details.
    2. Иначе ищем по имени через search_boardgame (exact=False), берем первый результат.
    """
    explicit_bgg_id = row.get("bgg_id")
    name = row.get("name")
    
    if explicit_bgg_id:
        logger.debug(f"Fetching BGG details by explicit ID: {explicit_bgg_id} for game: {name}")
        try:
            return get_boardgame_details(int(explicit_bgg_id))
        except Exception as e:
            logger.warning(f"Failed to fetch BGG details by ID {explicit_bgg_id}: {e}")
            return None

    if not name:
        logger.debug("No name provided in row, skipping BGG fetch")
        return None

    logger.debug(f"Searching BGG for game: {name}")
    try:
        found = search_boardgame(name, exact=False)
        if not found:
            logger.warning(f"No BGG results found for game: {name}")
            return None
        first = found[0]
        if not first.get("id"):
            logger.warning(f"BGG search result has no ID for game: {name}")
            return None
        logger.debug(f"Found BGG game ID {first['id']} for {name}, fetching details")
        return get_boardgame_details(first["id"])
    except Exception as e:
        logger.error(f"Error fetching BGG details for game {name}: {e}", exc_info=True)
        return None


def replace_all_from_table(
    session: Session,
    rows: List[Dict[str, Any]],
    *,
    is_forced_update: bool = False,
) -> None:
    """
    Обновляет данные об играх и оценках на основе табличных данных.

    Отличия от предыдущей версии:
    - больше НЕ удаляет игры и рейтинги целиком;
    - для каждой игры делает запрос к BGG и сохраняет все доступные поля;
    - поле мирового рейтинга (bgg_rank) и сопутствующие метаданные
      всегда подтягиваются по API, а не из таблицы;
    - добавлено управление частотой обновлений через is_forced_update.

    Ожидаемый формат rows:
    [
        {
            "name": str,
            "bgg_id": int | None,          # (опционально) явный ID на BGG
            "niza_games_rank": int | None,
            "genre": str | None,
            "ratings": { "user_name": int, ... }
        },
        ...
    ]
    """
    logger.info(f"Starting import from table: {len(rows)} rows, forced_update={is_forced_update}")
    
    # Рейтинги пересоздаем полностью, чтобы структура оставалась консистентной
    deleted_ratings = session.query(RatingModel).delete()
    logger.info(f"Deleted {deleted_ratings} existing ratings")

    games_created = 0
    games_updated = 0
    games_bgg_updated = 0
    ratings_added = 0

    for idx, row in enumerate(rows, 1):
        name = row.get("name")
        if not name:
            logger.debug(f"Skipping row {idx}: no name")
            continue

        # Ищем игру по имени (можно доработать до поиска по bgg_id при необходимости)
        game: GameModel | None = (
            session.query(GameModel)
            .filter(GameModel.name == name)
            .one_or_none()
        )

        if game is None:
            game = GameModel(name=name)
            session.add(game)
            session.flush()
            games_created += 1
            logger.debug(f"Created new game: {name}")
        else:
            games_updated += 1
            logger.debug(f"Updating existing game: {name}")

        # Всегда обновляем "локальные" поля из таблицы
        game.niza_games_rank = row.get("niza_games_rank")
        game.genre = _parse_genre(row.get("genre"))

        # Решаем, нужно ли идти в BGG за свежими данными
        if _should_update_game(game, is_forced_update):
            details = _fetch_bgg_details_for_row(row)
            if details:
                game.bgg_id = details.get("id")
                game.bgg_rank = details.get("rank")
                game.yearpublished = details.get("yearpublished")
                game.bayesaverage = details.get("bayesaverage")
                game.usersrated = details.get("usersrated")
                game.image = details.get("image")
                game.thumbnail = details.get("thumbnail")
                game.description = details.get("description")
                games_bgg_updated += 1
                logger.debug(f"Updated BGG data for game: {name}")

        session.flush()

        # Добавляем рейтинги для игры
        ratings = row.get("ratings") or {}
        for user_name, rank in ratings.items():
            rating = RatingModel(
                user_name=user_name,
                game_id=game.id,
                rank=int(rank),
            )
            session.add(rating)
            ratings_added += 1

    logger.info(
        f"Import completed: created={games_created}, updated={games_updated}, "
        f"bgg_updated={games_bgg_updated}, ratings_added={ratings_added}"
    )

