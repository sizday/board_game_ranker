from __future__ import annotations

import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message


router = Router()


@router.message(Command("game"))
async def cmd_game(message: Message, api_base_url: str) -> None:
    """
    Команда /game <название игры>

    Ищет игру на BGG через backend и возвращает информацию и картинку.
    """
    # Ожидаем, что пользователь напишет: /game Название игры
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Пожалуйста, укажи название игры. Пример:\n/game Terraforming Mars")
        return

    query = parts[1].strip()
    if not query:
        await message.answer("Название игры не должно быть пустым.")
        return

    await message.answer(f"Ищу игру «{query}» на BGG...")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{api_base_url}/api/bgg/search",
                params={"name": query, "exact": False},
                timeout=30.0,
            )
            resp.raise_for_status()

        data = resp.json()
        games = data.get("games") or []
        if not games:
            await message.answer("Не нашёл игр с таким названием 😔")
            return

        game = games[0]

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
        await message.answer(f"Ошибка при запросе к backend: {exc.response.status_code}")
    except Exception as exc:  # noqa: BLE001
        await message.answer(f"Не удалось получить данные об игре: {exc}")


