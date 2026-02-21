from __future__ import annotations

import logging
import httpx
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

logger = logging.getLogger(__name__)

router = Router()


class LoginStates(StatesGroup):
    waiting_for_name = State()


@router.message(Command("login"))
async def cmd_login(message: Message, state: FSMContext, api_base_url: str) -> None:
    """
    Команда /login - регистрирует пользователя в системе или позволяет изменить имя.

    Сначала проверяет, зарегистрирован ли пользователь, затем запрашивает имя.
    """
    user_id = message.from_user.id
    user_full_name = message.from_user.full_name or f"User_{user_id}"

    logger.info(f"User {user_full_name} (ID: {user_id}) initiated login")

    # Проверяем, зарегистрирован ли пользователь
    try:
        async with httpx.AsyncClient() as client:
            # Проверяем существование пользователя через GET запрос
            response = await client.get(
                f"{api_base_url}/api/users/{user_id}/games",
                timeout=10.0
            )

            if response.status_code == 200:
                # Пользователь уже зарегистрирован
                user_data = response.json()
                current_name = "Неизвестно"  # В текущем API нет информации об имени в этом эндпоинте

                # Получаем информацию о пользователе другим способом
                # Пока что просто предложим изменить имя
                await message.answer(
                    "👋 Ты уже зарегистрирован в системе!\n\n"
                    "Если хочешь изменить своё имя, введи новое имя ниже.\n"
                    "Если хочешь оставить текущее имя, просто отправь /cancel"
                )
            elif response.status_code == 404:
                # Пользователь не зарегистрирован
                await message.answer(
                    "👋 Привет! Для регистрации в системе мне нужно знать, как тебя называть.\n\n"
                    "Введи своё имя (то, под которым ты хочешь быть известен в системе):"
                )
            else:
                response.raise_for_status()

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            # Пользователь не зарегистрирован
            await message.answer(
                "👋 Привет! Для регистрации в системе мне нужно знать, как тебя называть.\n\n"
                "Введи своё имя (то, под которым ты хочешь быть известен в системе):"
            )
        else:
            logger.error(f"HTTP error during user check: {exc.response.status_code}")
            await message.answer(f"❌ Ошибка сервера: {exc.response.status_code}")
            return
    except Exception as exc:
        logger.error(f"Error during user check: {exc}", exc_info=True)
        await message.answer(f"❌ Не удалось проверить статус пользователя: {exc}")
        return

    # Устанавливаем состояние ожидания имени
    await state.set_state(LoginStates.waiting_for_name)


@router.message(StateFilter(LoginStates.waiting_for_name))
async def process_name_input(message: Message, state: FSMContext, api_base_url: str) -> None:
    """
    Обрабатывает введенное пользователем имя для регистрации или обновления.
    """
    user_id = message.from_user.id
    user_name = message.text.strip()

    # Валидация имени
    if not user_name:
        await message.answer("❌ Имя не может быть пустым. Введи своё имя:")
        return

    if len(user_name) > 100:
        await message.answer("❌ Имя слишком длинное (максимум 100 символов). Введи короче:")
        return

    logger.info(f"Processing name input for user {user_id}: '{user_name}'")

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
            created = user_data.get("created", False)
            name_updated = user_data.get("name_updated", False)

            # Очищаем состояние
            await state.clear()

            if created:
                # Новый пользователь
                logger.info(f"User {user_name} (telegram_id: {user_id}) successfully registered")
                await message.answer(
                    f"✅ Отлично, {user_name}!\n\n"
                    "Ты успешно зарегистрирован в системе.\n"
                    "Теперь можешь использовать команду /my_games для просмотра своих игр."
                )
            elif name_updated:
                # Имя обновлено
                logger.info(f"User {user_name} (telegram_id: {user_id}) name updated")
                await message.answer(
                    f"✅ Имя успешно изменено на '{user_name}'!\n\n"
                    "Теперь можешь использовать команду /my_games для просмотра своих игр."
                )
            else:
                # Пользователь уже существует с таким же именем
                logger.info(f"User {user_name} (telegram_id: {user_id}) already exists with same name")
                await message.answer(
                    f"👋 Привет, {user_name}!\n\n"
                    "Ты уже зарегистрирован в системе с таким именем.\n"
                    "Можешь использовать команду /my_games для просмотра своих игр."
                )

    except httpx.HTTPStatusError as exc:
        # Очищаем состояние даже при ошибке
        await state.clear()

        if exc.response.status_code == 400:
            try:
                error_data = exc.response.json()
                error_msg = error_data.get("detail", "Неизвестная ошибка")
            except:
                error_msg = "Ошибка валидации данных"
            await message.answer(f"❌ Ошибка: {error_msg}")
        else:
            logger.error(f"HTTP error during user registration: {exc.response.status_code}")
            await message.answer(f"❌ Ошибка сервера: {exc.response.status_code}")
    except Exception as exc:
        # Очищаем состояние даже при ошибке
        await state.clear()

        logger.error(f"Error during user registration: {exc}", exc_info=True)
        await message.answer(f"❌ Не удалось зарегистрироваться: {exc}")


@router.message(Command("cancel"), StateFilter(LoginStates.waiting_for_name))
async def cancel_login(message: Message, state: FSMContext) -> None:
    """
    Отменяет процесс регистрации/изменения имени.
    """
    await state.clear()
    await message.answer("❌ Операция отменена.")