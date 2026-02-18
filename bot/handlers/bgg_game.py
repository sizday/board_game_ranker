from __future__ import annotations

import logging
import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("game"))
async def cmd_game(message: Message, api_base_url: str) -> None:
    """
    Команда /game <название игры>

    Ищет игру на BGG через backend и возвращает информацию и картинку.
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
    await message.answer(f"Ищу игру «{query}» на BGG...")

    try:
        async with httpx.AsyncClient() as client:
            # Запрашиваем только первую игру для оптимизации
            resp = await client.get(
                f"{api_base_url}/api/bgg/search",
                params={"name": query, "exact": False, "limit": 1},
                timeout=30.0,
            )
            resp.raise_for_status()

        data = resp.json()
        games = data.get("games") or []
        if not games:
            logger.info(f"No games found for query: {query}")
            await message.answer("Не нашёл игр с таким названием 😔")
            return

        game = games[0]
        logger.info(f"Found game: {game.get('name')} (rank: {game.get('rank')})")

        name = game.get("name") or "Без названия"
        year = game.get("yearpublished")
        rank = game.get("rank")
        bayes = game.get("bayesaverage")
        users = game.get("usersrated")
        image = game.get("image")

        lines = [f"<b>{name}</b>"]
        if year:
            lines.append(f"Год: {year}")
        if rank:
            lines.append(f"Мировой рейтинг BGG: #{rank}")
        if bayes is not None:
            lines.append(f"Оценка (Bayes avg): {bayes:.2f}")
        if users:
            lines.append(f"Голосов: {users}")

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


