from __future__ import annotations

import logging
import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("my_games"))
async def cmd_my_games(message: Message, api_base_url: str) -> None:
    """
    Команда /my_games - показывает список игр пользователя с ссылками на BGG.

    Показывает только игры с BGG ID, отсортированные лексикографически.
    """
    user_id = message.from_user.id
    user_name = message.from_user.full_name or str(user_id)

    logger.info(f"User {user_name} (ID: {user_id}) requested their games")

    try:
        # Сначала получаем информацию о пользователе
        async with httpx.AsyncClient() as client:
            # Проверяем, зарегистрирован ли пользователь
            user_response = await client.get(
                f"{api_base_url}/api/users/{user_id}/games",
                timeout=10.0
            )
            user_response.raise_for_status()

            data = user_response.json()
            games = data.get("games", [])

            if not games:
                await message.answer(
                    "📭 У тебя пока нет оцененных игр.\n\n"
                    "Чтобы добавить игры:\n"
                    "1. Зарегистрируйся командой /login\n"
                    "2. Дождись импорта данных администратором (/import)\n"
                    "3. Твои игры появятся в этом списке!"
                )
                return

            # Формируем сообщение со списком игр
            lines = [f"🎲 Твои игры ({len(games)}):\n"]

            for game in games:
                name = game.get("name", "Без названия")
                bgg_url = game.get("bgg_url", "")
                rank = game.get("rank")
                year = game.get("year")

                # Формируем строку с игрой
                game_line = f"• <a href=\"{bgg_url}\">{name}</a>"
                if year:
                    game_line += f" ({year})"
                if rank:
                    game_line += f" [#{rank}]"

                lines.append(game_line)

            # Разбиваем на части, если сообщение слишком длинное
            text = "\n".join(lines)
            if len(text) > 4000:  # Ограничение Telegram
                # Разбиваем на части по 20 игр
                parts = []
                current_part = []
                for i, line in enumerate(lines):
                    current_part.append(line)
                    if (i + 1) % 20 == 0 or i == len(lines) - 1:
                        parts.append("\n".join(current_part))
                        current_part = []

                for part in parts:
                    await message.answer(part, disable_web_page_preview=True)
            else:
                await message.answer(text, disable_web_page_preview=True)

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            await message.answer(
                "❌ Ты не зарегистрирован в системе.\n\n"
                "Используй команду /login для регистрации."
            )
        else:
            logger.error(f"HTTP error getting user games: {exc.response.status_code}")
            await message.answer(f"❌ Ошибка сервера: {exc.response.status_code}")
    except Exception as exc:
        logger.error(f"Error getting user games: {exc}", exc_info=True)
        await message.answer(f"❌ Не удалось получить список игр: {exc}")