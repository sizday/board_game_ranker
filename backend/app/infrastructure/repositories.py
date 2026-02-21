import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Callable

from sqlalchemy.orm import Session

from app.config import config
from app.domain.models import GameGenre
from app.services.bgg import get_boardgame_details, search_boardgame
from .models import GameModel, RatingModel, RankingSessionModel, UserModel

logger = logging.getLogger(__name__)


GAME_UPDATE_DELTA = timedelta(days=config.GAME_UPDATE_DAYS)


def get_or_create_user(session: Session, telegram_id: int, name: str) -> tuple[UserModel, bool, bool]:
    """
    Получает существующего пользователя по telegram_id или создает нового.

    :param session: Сессия базы данных
    :param telegram_id: Telegram ID пользователя
    :param name: Имя пользователя
    :return: Кортеж (модель пользователя, создан ли новый, изменено ли имя)
    """
    user = session.query(UserModel).filter(UserModel.telegram_id == telegram_id).first()

    created = False
    name_changed = False

    if user is None:
        user = UserModel(name=name, telegram_id=telegram_id)
        session.add(user)
        session.flush()
        created = True
        logger.info(f"Created new user: {name} (telegram_id: {telegram_id})")
    else:
        # Обновляем имя, если оно изменилось
        if user.name != name:
            old_name = user.name
            user.name = name
            name_changed = True
            logger.info(f"Updated user name from '{old_name}' to '{name}' (telegram_id: {telegram_id})")

    return user, created, name_changed


def get_user_games_with_bgg_links(session: Session, user_id: str) -> List[Dict[str, Any]]:
    """
    Получает список игр пользователя с ссылками на BGG, отсортированный лексикографически.

    :param session: Сессия базы данных
    :param user_id: ID пользователя
    :return: Список игр с информацией о BGG
    """
    from uuid import UUID

    games = (
        session.query(GameModel)
        .join(RatingModel)
        .filter(
            RatingModel.user_id == UUID(user_id),
            RatingModel.rank > 0,  # Только игры с оценками (не 0)
            GameModel.bgg_id.isnot(None)  # Только игры с BGG ID
        )
        .order_by(GameModel.name)  # Лексикографическая сортировка
        .all()
    )

    result = []
    for game in games:
        result.append({
            "id": str(game.id),
            "name": game.name,
            "bgg_id": game.bgg_id,
            "bgg_url": f"https://boardgamegeek.com/boardgame/{game.bgg_id}",
            "rank": game.bgg_rank,
            "year": game.yearpublished,
        })

    return result


def save_game_from_bgg_data(
    session: Session,
    bgg_data: Dict[str, Any],
) -> GameModel:
    """
    Сохраняет или обновляет игру в БД на основе данных из BGG API.

    :param session: Сессия базы данных
    :param bgg_data: Данные игры из BGG API
    :return: Модель игры
    """
    game_id = bgg_data.get("id")
    name = bgg_data.get("name")

    if not game_id or not name:
        raise ValueError("BGG data must contain 'id' and 'name' fields")

    # Ищем существующую игру по bgg_id или имени
    game: GameModel | None = (
        session.query(GameModel)
        .filter(GameModel.bgg_id == game_id)
        .one_or_none()
    )

    if game is None:
        # Ищем по имени, если bgg_id не найден
        game = (
            session.query(GameModel)
            .filter(GameModel.name == name)
            .one_or_none()
        )

    if game is None:
        # Создаем новую игру
        game = GameModel(name=name)
        session.add(game)
        logger.info(f"Created new game from BGG data: {name} (bgg_id: {game_id})")

    # Обновляем все поля данными из BGG
    game.bgg_id = game_id
    game.bgg_rank = bgg_data.get("rank")
    game.yearpublished = bgg_data.get("yearpublished")
    game.bayesaverage = bgg_data.get("bayesaverage")
    game.usersrated = bgg_data.get("usersrated")
    game.minplayers = bgg_data.get("minplayers")
    game.maxplayers = bgg_data.get("maxplayers")
    game.playingtime = bgg_data.get("playingtime")
    game.minplaytime = bgg_data.get("minplaytime")
    game.maxplaytime = bgg_data.get("maxplaytime")
    game.minage = bgg_data.get("minage")
    game.average = bgg_data.get("average")
    game.numcomments = bgg_data.get("numcomments")
    game.owned = bgg_data.get("owned")
    game.trading = bgg_data.get("trading")
    game.wanting = bgg_data.get("wanting")
    game.wishing = bgg_data.get("wishing")
    game.averageweight = bgg_data.get("averageweight")
    game.numweights = bgg_data.get("numweights")
    game.categories = bgg_data.get("categories")
    game.mechanics = bgg_data.get("mechanics")
    game.designers = bgg_data.get("designers")
    game.publishers = bgg_data.get("publishers")
    game.image = bgg_data.get("image")
    game.thumbnail = bgg_data.get("thumbnail")
    game.description = bgg_data.get("description")
    # description_ru будет заполнен позже через фоновый перевод

    session.flush()
    action = "updated" if game.bgg_id == game_id else "created"
    logger.info(f"💾 Game {action}: '{name}' (DB ID: {game.id}, BGG ID: {game_id})")

    if game.description:
        logger.debug(f"📝 Game '{name}' has description ({len(game.description)} chars)")
    else:
        logger.debug(f"📝 Game '{name}' has no description")

    return game


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

    Обновляем в следующих случаях:
    - is_forced_update=True (принудительное обновление)
    - Новая игра (нет bgg_id - данные из BGG не загружались)
    - Существующая игра, данные которой старше 30 дней
    """
    if is_forced_update:
        logger.debug(f"Forced update requested for game: {game.name}")
        return True

    # Новая игра - нет данных из BGG
    if not game.bgg_id:
        logger.debug(f"Game {game.name} has no BGG ID, update needed")
        return True

    # Существующая игра - проверяем дату последнего обновления
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

    Приоритет выбора кандидата:
    1. Если в строке есть явный bgg_id — сразу дергаем get_boardgame_details.
    2. Иначе ищем по имени через search_boardgame (exact=False), выбираем наиболее релевантный результат:
       - Сначала точные совпадения названия
       - Затем основные игры (boardgame) перед расширениями (boardgameexpansion)
       - Затем по мировому рейтингу (выше рейтинг = выше приоритет)
       - Наконец по количеству голосов (больше голосов = выше приоритет)
    """
    explicit_bgg_id = row.get("bgg_id")
    name = row.get("name")

    if explicit_bgg_id:
        logger.debug(f"Fetching BGG details by explicit ID: {explicit_bgg_id} for game: {name}")
        try:
            result = get_boardgame_details(int(explicit_bgg_id))
            # Задержка между запросами для избежания rate limiting
            time.sleep(config.BGG_REQUEST_DELAY)
            return result
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
            logger.warning(f"❌ No BGG search results found for game: '{name}'")
            return None

        # Получаем детали для большего количества кандидатов для выбора лучшего
        candidates_limit = min(len(found), 5)  # Берем до 5 кандидатов для сортировки
        candidates: List[Dict[str, Any]] = []

        for idx, item in enumerate(found[:candidates_limit], 1):
            try:
                game_id = item.get("id")
                if not game_id:
                    logger.warning(f"Пропущен item без id: {item}")
                    continue

                logger.debug(f"Загрузка деталей кандидата {idx}/{candidates_limit}: game_id={game_id}")
                details = get_boardgame_details(game_id)
                logger.debug(f"Получены детали для game_id={game_id}: name='{details.get('name')}', type='{details.get('type')}', rank={details.get('rank')}")
                candidates.append(details)
                # Задержка между запросами для избежания rate limiting
                time.sleep(config.BGG_REQUEST_DELAY)
            except Exception as e:
                logger.error(f"Ошибка при загрузке деталей кандидата game_id={item.get('id')}: {e}", exc_info=True)
                continue

        if not candidates:
            logger.warning(f"❌ Failed to load details for any BGG candidates for game: '{name}' (found {len(found)} candidates)")
            return None

        # Сортируем кандидатов по релевантности:
        # 1. Сначала игры с точным совпадением названия (без учета регистра)
        # 2. Затем ОСНОВНЫЕ ИГРЫ имеют абсолютный приоритет перед расширениями
        # 3. Затем по мировому рейтингу (меньше число = выше рейтинг)
        # 4. Наконец по количеству голосов (больше = лучше)
        def sort_key(candidate: Dict[str, Any]) -> tuple:
            candidate_name = (candidate.get("name") or '').lower()
            query_name = name.lower()
            exact_match = candidate_name == query_name

            # Дополнительная проверка: если название кандидата намного длиннее искомого,
            # это может быть расширение или связанная игра (например, "Expansion for Game Name")
            name_length_ratio = len(candidate_name) / len(query_name) if query_name else 1
            is_likely_expansion = name_length_ratio > 2.0 and not exact_match  # Название в 2+ раза длиннее и не точное совпадение

            # Определяем приоритет по типу игры - ОСНОВНЫЕ ИГРЫ имеют абсолютный приоритет
            game_type = candidate.get("type", "").lower()
            is_base_game = game_type == "boardgame"  # Основная игра имеет приоритет
            # Увеличиваем штраф для расширений и вероятно-расширений
            game_type_priority = 0 if is_base_game else 1000000  # Огромный штраф для расширений
            if is_likely_expansion:
                game_type_priority += 500000  # Дополнительный штраф для вероятно-расширений

            rank = candidate.get("rank") or 999999
            users_rated = candidate.get("usersrated") or 0

            return (
                0 if exact_match else 1,      # Точное совпадение первым
                game_type_priority,           # ОСНОВНЫЕ ИГРЫ имеют абсолютный приоритет
                rank,                         # Лучший рейтинг (меньше число = выше)
                -users_rated                  # Больше голосов
            )

        candidates_sorted = sorted(candidates, key=sort_key)
        best_candidate = candidates_sorted[0]

        # Логируем всех кандидатов для диагностики
        logger.info(f"🎯 Выбор лучшего кандидата для '{name}' из {len(candidates)} вариантов:")
        for i, candidate in enumerate(candidates_sorted[:5], 1):  # Показываем топ-5
            game_type = candidate.get("type", "unknown")
            rank = candidate.get("rank", "N/A")
            users_rated = candidate.get("usersrated", 0)
            exact_match_indicator = "✓" if (candidate.get("name") or '').lower() == name.lower() else "✗"
            sort_key_value = sort_key(candidate)
            logger.info(f"  {i}. [{exact_match_indicator}] '{candidate.get('name')}' (ID: {candidate.get('id')}, Type: {game_type}, Rank: {rank}, Users: {users_rated}) | Sort key: {sort_key_value}")

        logger.info(f"✅ Выбран кандидат: '{best_candidate.get('name')}' (ID: {best_candidate.get('id')}, Type: {best_candidate.get('type')}, Rank: {best_candidate.get('rank')})")

        return best_candidate

    except Exception as e:
        logger.error(f"Error fetching BGG details for game {name}: {e}", exc_info=True)
        return None


def replace_all_from_table(
    session: Session,
    rows: List[Dict[str, Any]],
    *,
    is_forced_update: bool = False,
) -> int:
    """
    Обновляет данные об играх и оценках на основе табличных данных.

    Отличия от предыдущей версии:
    - больше НЕ удаляет игры и рейтинги целиком;
    - рейтинги добавляются/обновляются последовательно вместе с играми;
    - для каждой игры делает запрос к BGG и сохраняет все доступные поля;
    - поле мирового рейтинга (bgg_rank) и сопутствующие метаданные
      всегда подтягиваются по API, а не из таблицы;
    - локальные поля (niza_games_rank, genre, description_ru) всегда обновляются из таблицы;
    - добавлено управление частотой обновлений через is_forced_update.

    Ожидаемый формат rows:
    [
        {
            "name": str,
            "bgg_id": int | None,          # (опционально) явный ID на BGG
            "niza_games_rank": int | None,
            "genre": str | None,
            "description_ru": str | None,  # (опционально) русский перевод описания
            "ratings": { "user_name": int, ... }  # рейтинг 1-50, где 0 = не оценивал
        },
        ...
    ]
    """
    logger.info(f"Starting import from table: {len(rows)} rows, forced_update={is_forced_update}")

    # Логируем структуру данных для диагностики
    if rows:
        logger.debug(f"Sample row structure: {rows[0]}")
        logger.debug(f"Row keys: {list(rows[0].keys())}")
    else:
        logger.warning("No rows to process!")
        return
    
    # Рейтинги добавляем/обновляем последовательно вместе с играми
    # (не удаляем существующие, чтобы сохранить историю)

    games_created = 0
    games_updated = 0
    games_bgg_updated = 0
    games_bgg_not_found = 0
    ratings_added = 0
    ratings_updated = 0

    for idx, row in enumerate(rows, 1):
        try:
            name = row.get("name")
            if not name:
                logger.debug(f"Skipping row {idx}: no name")
                continue

            # Валидируем структуру данных
            if not isinstance(row, dict):
                logger.warning(f"Skipping row {idx}: not a dict, got {type(row)}")
                continue

            # Проверяем, что name является строкой
            if not isinstance(name, str):
                logger.warning(f"Skipping row {idx}: name is not string, got {type(name)}")
                continue

            name = name.strip()
            if not name:
                logger.debug(f"Skipping row {idx}: empty name after strip")
                continue

            logger.debug(f"Processing row {idx}: game='{name}'")

        except Exception as e:
            logger.warning(f"Error validating row {idx}: {e}")
            continue

        # Обработка каждой игры в отдельном try/catch для изоляции ошибок
        try:
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

            # Всегда обновляем "локальные" поля из таблицы (niza_games_rank, genre, description_ru)
            niza_rank = row.get("niza_games_rank")
            if niza_rank is not None:
                try:
                    game.niza_games_rank = int(niza_rank) if niza_rank != "" else None
                except (ValueError, TypeError):
                    logger.warning(f"Invalid niza_games_rank value for game '{name}': {niza_rank}")
                    game.niza_games_rank = None
            else:
                game.niza_games_rank = None

            game.genre = _parse_genre(row.get("genre"))

            # Обновляем русский перевод, если он есть в таблице
            description_ru = row.get("description_ru")
            if description_ru is not None and description_ru.strip():
                game.description_ru = description_ru.strip()
                logger.debug(f"Updated Russian description for game '{name}' from table")
            # Если поле пустое или отсутствует, не трогаем существующее значение

            # Решаем, нужно ли идти в BGG за свежими данными
            if _should_update_game(game, is_forced_update):
                details = _fetch_bgg_details_for_row(row)
                if details:
                    game.bgg_id = details.get("id")
                    game.bgg_rank = details.get("rank")
                    game.yearpublished = details.get("yearpublished")
                    game.bayesaverage = details.get("bayesaverage")
                    game.usersrated = details.get("usersrated")
                    game.minplayers = details.get("minplayers")
                    game.maxplayers = details.get("maxplayers")
                    game.playingtime = details.get("playingtime")
                    game.minplaytime = details.get("minplaytime")
                    game.maxplaytime = details.get("maxplaytime")
                    game.minage = details.get("minage")
                    game.average = details.get("average")
                    game.numcomments = details.get("numcomments")
                    game.owned = details.get("owned")
                    game.trading = details.get("trading")
                    game.wanting = details.get("wanting")
                    game.wishing = details.get("wishing")
                    game.averageweight = details.get("averageweight")
                    game.numweights = details.get("numweights")
                    game.categories = details.get("categories")
                    game.mechanics = details.get("mechanics")
                    game.designers = details.get("designers")
                    game.publishers = details.get("publishers")
                    game.image = details.get("image")
                    game.thumbnail = details.get("thumbnail")
                    game.description = details.get("description")
                    games_bgg_updated += 1
                    logger.debug(f"Updated BGG data for game: {name}")
                else:
                    logger.warning(f"❌ Game '{name}' not found on BGG during import (row bgg_id: {row.get('bgg_id')})")
                    games_bgg_not_found += 1

            session.flush()

            # Добавляем рейтинги для игры
            ratings = row.get("ratings") or {}
            if not isinstance(ratings, dict):
                logger.warning(f"Invalid ratings format for game '{name}': expected dict, got {type(ratings)}")
                ratings = {}

            # Логируем пользователей для диагностики
            logger.warning(f"STARTING TO PROCESS RATINGS FOR GAME '{name}': {len(ratings)} users - {list(ratings.keys())}")

            for user_name, rank in ratings.items():
                try:
                    print(f"DEBUG: Processing rating for user '{user_name}' (rank: {rank})")
                    if not isinstance(user_name, str) or not user_name.strip():
                        continue

                    # Пропускаем специального пользователя "Общий" - это не настоящий пользователь
                    user_name_clean = user_name.strip().lower()
                    print(f"DEBUG: Checking user: '{user_name}' -> '{user_name_clean}'")
                    if 'общий' in user_name_clean or user_name_clean in ['general', 'общий рейтинг'] or user_name_clean == 'общий':
                        print(f"DEBUG: SKIPPING special user '{user_name}' for game '{name}'")
                        logger.error(f"SKIPPING special user '{user_name}' for game '{name}' - CONDITION MET")
                        continue
                    else:
                        print(f"DEBUG: NOT SKIPPING user '{user_name}' for game '{name}'")
                        logger.warning(f"NOT SKIPPING user '{user_name}' for game '{name}' - CONDITION NOT MET")

                    # rank может быть 0 (место для будущего рейтинга) или 1-50 (оценка)
                    if not isinstance(rank, int) or rank < 0 or rank > 50:
                        logger.warning(f"Invalid rank value for game '{name}', user '{user_name}': {rank} (type: {type(rank)})")
                        continue

                    # Ищем пользователя по имени (предполагаем, что имя в таблице соответствует имени пользователя)
                    user = session.query(UserModel).filter(UserModel.name == user_name.strip()).first()
                    if not user:
                        logger.warning(f"User '{user_name}' not found, skipping rating for game '{name}'")
                        continue

                    # Проверяем, существует ли уже рейтинг для этого пользователя и игры
                    existing_rating = session.query(RatingModel).filter(
                        RatingModel.user_id == user.id,
                        RatingModel.game_id == game.id
                    ).first()

                    if existing_rating:
                        # Обновляем существующий рейтинг
                        existing_rating.rank = rank
                        ratings_updated += 1
                        logger.debug(f"Updated rating for user '{user_name.strip()}' and game '{name}': {rank}")
                    else:
                        # Создаем новый рейтинг (включая 0 - место для будущего рейтинга)
                        rating = RatingModel(
                            user_id=user.id,
                            game_id=game.id,
                            rank=rank,
                        )
                        session.add(rating)
                        ratings_added += 1
                        logger.debug(f"Created rating for user '{user_name.strip()}' and game '{name}': {rank}")

                except (ValueError, TypeError) as e:
                    logger.warning(f"Error processing rating for game '{name}', user '{user_name}': {e}")
                    continue

            # Сохраняем изменения для этой игры
            session.commit()

        except Exception as e:
            logger.error(f"Error processing game '{name}' in row {idx}: {type(e).__name__}: {e}", exc_info=True)
            # Откатываем изменения для этой игры, но продолжаем обработку следующих
            session.rollback()
            continue

        # Небольшая задержка между обработкой игр для снижения нагрузки на API
        time.sleep(config.BGG_REQUEST_DELAY)

    # Примечание: рейтинги пользователя "общий" больше не создаются,
    # так как такого пользователя нет в таблице users

    session.commit()

    logger.info(
        f"Import completed: created={games_created}, updated={games_updated}, "
        f"bgg_updated={games_bgg_updated}, bgg_not_found={games_bgg_not_found}, "
        f"ratings_added={ratings_added}, ratings_updated={ratings_updated}"
    )

    # Возвращаем общее количество обработанных игр
    return games_created + games_updated


def clear_all_data(session: Session) -> Dict[str, int]:
    """
    Удаляет все данные из базы данных.

    Возвращает словарь с количеством удаленных записей по каждой таблице.
    """
    logger.info("Starting database cleanup")

    # Удаляем рейтинги (сначала, чтобы не было проблем с foreign keys)
    ratings_deleted = session.query(RatingModel).delete()
    logger.info(f"Deleted {ratings_deleted} ratings")

    # Удаляем сессии ранжирования
    sessions_deleted = session.query(RankingSessionModel).delete()
    logger.info(f"Deleted {sessions_deleted} ranking sessions")

    # Удаляем пользователей
    users_deleted = session.query(UserModel).delete()
    logger.info(f"Deleted {users_deleted} users")

    # Удаляем игры (последними, так как на них могут ссылаться рейтинги)
    games_deleted = session.query(GameModel).delete()
    logger.info(f"Deleted {games_deleted} games")

    logger.info(f"Database cleanup completed: games={games_deleted}, ratings={ratings_deleted}, sessions={sessions_deleted}, users={users_deleted}")

    return {
        "games_deleted": games_deleted,
        "ratings_deleted": ratings_deleted,
        "sessions_deleted": sessions_deleted,
        "users_deleted": users_deleted,
    }

