from __future__ import annotations

import logging
import httpx
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("login"))
async def cmd_login(message: Message, api_base_url: str) -> None:
    """
    Команда /login - регистрирует пользователя в системе.

    Использует имя из Telegram профиля пользователя.
    """
    user_id = message.from_user.id
    user_full_name = message.from_user.full_name or f"User_{user_id}"

    logger.info(f"User {user_full_name} (ID: {user_id}) initiated login")

    # Используем имя из Telegram профиля
    user_name = user_full_name.strip()

    if not user_name:
        await message.answer(
            "❌ Не удалось определить твоё имя из профиля Telegram.\n\n"
            "Установи имя в настройках Telegram и попробуй снова."
        )
        return

    logger.info(f"Registering user {user_id} with name: {user_name}")

    try:
        async with httpx.AsyncClient() as client:
            # Создаем или обновляем пользователя через API
            response = await client.post(
                f"{api_base_url}/api/users",
                json={
                    "telegram_id": user_id,
                    "name": user_name
                },
                timeout=10.0
            )
            response.raise_for_status()

            user_data = response.json()
            logger.info(f"User {user_name} (telegram_id: {user_id}) successfully registered")

            await message.answer(
                f"✅ Отлично, {user_name}!\n\n"
                "Ты успешно зарегистрирован в системе.\n"
                "Теперь можешь использовать команду /my_games для просмотра своих игр."
            )

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            try:
                error_data = exc.response.json()
                error_msg = error_data.get("detail", "Неизвестная ошибка")
            except:
                error_msg = "Ошибка валидации данных"
            await message.answer(f"❌ Ошибка регистрации: {error_msg}")
        else:
            logger.error(f"HTTP error during user registration: {exc.response.status_code}")
            await message.answer(f"❌ Ошибка сервера: {exc.response.status_code}")
    except Exception as exc:
        logger.error(f"Error during user registration: {exc}", exc_info=True)
        await message.answer(f"❌ Не удалось зарегистрироваться: {exc}")