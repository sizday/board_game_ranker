from __future__ import annotations

import logging
import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("game"))
async def cmd_game(message: Message, api_base_url: str, default_language: str) -> None:
    """
    Команда /game <название игры>

    Сначала ищет игру в базе данных, если не найдена - обращается к BGG API.
    Возвращает полную информацию и картинку.
    """
    user_id = message.from_user.id
    user_name = message.from_user.full_name or str(user_id)

    # Ожидаем, что пользователь напишет: /game Название игры
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        logger.debug(f"User {user_name} sent /game without query")
        await message.answer("Пожалуйста, укажи название игры. Пример:\n/game Terraforming Mars")
        return

    query = parts[1].strip()
    if not query:
        logger.debug(f"User {user_name} sent empty game query")
        await message.answer("Название игры не должно быть пустым.")
        return

    logger.info(f"User {user_name} (ID: {user_id}) searching for game: {query}")

    game = None
    search_source = ""

    try:
        async with httpx.AsyncClient() as client:
            # Сначала ищем в базе данных
            logger.debug(f"Searching in database first: {query}")
            await message.answer(f"Ищу игру «{query}»...")

            resp = await client.get(
                f"{api_base_url}/api/games/search",
                params={"name": query, "exact": False, "limit": 1},
                timeout=10.0,
            )
            resp.raise_for_status()

            data = resp.json()
            games_db = data.get("games") or []

            if games_db:
                # Нашли в базе данных
                game = games_db[0]
                search_source = "database"
                logger.info(f"Found game in database: {game.get('name')} (id: {game.get('id')})")
            else:
                # Не нашли в БД, ищем на BGG
                logger.info(f"Game not found in database, searching BGG: {query}")
                await message.answer("Игра не найдена в базе данных, ищу на BGG...")

                resp = await client.get(
                    f"{api_base_url}/api/bgg/search",
                    params={"name": query, "exact": False, "limit": 1},
                    timeout=30.0,
                )
                resp.raise_for_status()

                data = resp.json()
                games_bgg = data.get("games") or []

                if games_bgg:
                    game = games_bgg[0]
                    search_source = "bgg"
                    logger.info(f"Found game on BGG: {game.get('name')} (rank: {game.get('rank')})")

                    # Сохраняем игру в базу данных для будущих запросов
                    try:
                        async with httpx.AsyncClient() as client:
                            save_resp = await client.post(
                                f"{api_base_url}/api/games/save-from-bgg",
                                json=game,
                                timeout=10.0,
                            )
                            save_resp.raise_for_status()
                            logger.info(f"Successfully saved game to database: {game.get('name')}")
                    except Exception as save_exc:
                        logger.warning(f"Failed to save game to database: {save_exc}")
                        # Продолжаем работу, даже если сохранение не удалось
                else:
                    logger.info(f"No games found for query: {query}")
                    await message.answer("Не нашёл игр с таким названием 😔")
                    return

    except httpx.HTTPStatusError as exc:
        logger.error(f"HTTP error searching for game '{query}': {exc.response.status_code}")
        await message.answer(f"Ошибка при запросе к backend: {exc.response.status_code}")
        return
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error searching for game '{query}': {exc}", exc_info=True)
        await message.answer(f"Не удалось получить данные об игре: {exc}")
        return

        # Извлекаем данные игры (работает для обоих источников)
        name = game.get("name") or "Без названия"
        year = game.get("yearpublished")
        minplayers = game.get("minplayers")
        maxplayers = game.get("maxplayers")
        playingtime = game.get("playingtime")
        minage = game.get("minage")
        # Для игр из БД используем bgg_rank, для BGG API - rank
        rank = game.get("bgg_rank") or game.get("rank")
        avg = game.get("average")
        bayes = game.get("bayesaverage")
        users = game.get("usersrated")
        weight = game.get("averageweight")
        categories = game.get("categories") or []
        mechanics = game.get("mechanics") or []
        image = game.get("image")
        description = game.get("description")

        # Выбираем описание в зависимости от языка
        original_lang = "en"
        if default_language == "ru":
            description_ru = game.get("description_ru")
            if description_ru:
                description = description_ru
                original_lang = "ru"
                logger.debug(f"🌍 Using Russian description for game: {name}")
            else:
                logger.debug(f"🌍 No Russian description available for game: {name}, using English")

        logger.info(f"📖 Displaying game '{name}' from {search_source} (rank: #{rank}, lang: {original_lang})")

        lines = [f"<b>{name}</b>"]
        if year:
            lines.append(f"Год: {year}")
        if minplayers or maxplayers:
            if minplayers and maxplayers and minplayers != maxplayers:
                lines.append(f"Игроки: {minplayers}–{maxplayers}")
            else:
                lines.append(f"Игроки: {minplayers or maxplayers}")
        if playingtime:
            lines.append(f"Время: ~{playingtime} мин")
        if minage:
            lines.append(f"Возраст: {minage}+")
        if rank:
            lines.append(f"Мировой рейтинг BGG: #{rank}")
        if avg is not None:
            try:
                lines.append(f"Оценка (avg): {float(avg):.2f}")
            except Exception:  # noqa: BLE001
                pass
        if bayes is not None:
            lines.append(f"Оценка (Bayes avg): {bayes:.2f}")
        if users:
            lines.append(f"Голосов: {users}")
        if weight is not None:
            try:
                lines.append(f"Сложность (weight): {float(weight):.2f}/5")
            except Exception:  # noqa: BLE001
                pass
        if categories:
            short = ", ".join(categories[:5])
            lines.append(f"Категории: {short}" + ("…" if len(categories) > 5 else ""))
        if mechanics:
            short = ", ".join(mechanics[:5])
            lines.append(f"Механики: {short}" + ("…" if len(mechanics) > 5 else ""))
        if description:
            # Telegram ограничивает длину сообщения; даём короткий фрагмент
            snippet = description[:350]
            if len(description) > 350:
                snippet += "…"
            lines.append(f"\nОписание: {snippet}")

        text = "\n".join(lines)

        if image:
            await message.answer_photo(photo=image, caption=text)
        else:
            await message.answer(text)
    except httpx.HTTPStatusError as exc:
        logger.error(f"HTTP error searching for game '{query}': {exc.response.status_code}")
        await message.answer(f"Ошибка при запросе к backend: {exc.response.status_code}")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error searching for game '{query}': {exc}", exc_info=True)
        await message.answer(f"Не удалось получить данные об игре: {exc}")


