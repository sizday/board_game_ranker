from __future__ import annotations

import logging
import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

logger = logging.getLogger(__name__)

router = Router()


async def _handle_phase_transition(
    callback: CallbackQuery,
    state: FSMContext,
    payload: dict,
    session_id: int,
) -> None:
    """Обрабатывает переходы между состояниями на основе phase из API ответа."""
    phase = payload.get("phase")

    if phase == "first_tier":
        await state.set_state(RankingStates.first_tier)
        game = payload["next_game"]
        usersrated = game.get("usersrated")
        usersrated_text = f" (👥 {usersrated})" if usersrated else ""
        year = game.get("yearpublished")
        year_text = f" ({year})" if year else ""
        bgg_rank = game.get("bgg_rank")
        bgg_text = f"\nBGG: #{bgg_rank}" if bgg_rank else ""
        text = (
            f"Игра: <b>{game['name']}</b>{year_text}{usersrated_text}{bgg_text}\n"
            f"Отметь, насколько она тебе понравилась."
        )
        thumbnail = game.get("thumbnail")
        if thumbnail:
            await callback.message.answer_photo(
                photo=thumbnail,
                caption=text,
                reply_markup=_first_tier_keyboard(
                    session_id=session_id,
                    game_id=game["id"],
                ),
            )
        else:
            await callback.message.answer(
                text,
                reply_markup=_first_tier_keyboard(
                    session_id=session_id,
                    game_id=game["id"],
                ),
            )
    elif phase == "second_tier":
        await state.set_state(RankingStates.second_tier)
        game = payload["next_game"]
        usersrated = game.get("usersrated")
        usersrated_text = f" (👥 {usersrated})" if usersrated else ""
        year = game.get("yearpublished")
        year_text = f" ({year})" if year else ""
        bgg_rank = game.get("bgg_rank")
        bgg_text = f"\nBGG: #{bgg_rank}" if bgg_rank else ""
        text = (
            "Отлично! Теперь уточним, какие игры прямо топчик.\n\n"
            f"Игра: <b>{game['name']}</b>{year_text}{usersrated_text}{bgg_text}\n"
            f"Выбери, насколько она крутая."
        )
        thumbnail = game.get("thumbnail")
        if thumbnail:
            await callback.message.answer_photo(
                photo=thumbnail,
                caption=text,
                reply_markup=_second_tier_keyboard(
                    session_id=session_id,
                    game_id=game["id"],
                ),
            )
        else:
            await callback.message.answer(
                text,
                reply_markup=_second_tier_keyboard(
                    session_id=session_id,
                    game_id=game["id"],
                ),
            )
    elif phase == "final":
        await state.set_state(RankingStates.final)
        top = payload.get("top", [])
        lines = []
        for item in top:
            rank = item.get("rank", "")
            name = item.get("name", "")
            usersrated = item.get("usersrated")
            year = item.get("yearpublished")
            year_text = f" ({year})" if year else ""
            if usersrated:
                lines.append(f"{rank}. {name}{year_text} (👥 {usersrated})")
            else:
                lines.append(f"{rank}. {name}{year_text}")
        text = "Твой предварительный топ-50:\n\n" + "\n".join(lines)
        await callback.message.edit_text(text)
    elif phase == "completed":
        await state.set_state(RankingStates.completed)
        await callback.message.edit_text(payload.get("message", "Готово."))


class RankingStates(StatesGroup):
    first_tier = State()
    second_tier = State()
    final = State()
    completed = State()


def _first_tier_keyboard(session_id: int, game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="😕 Плохо",
                    callback_data=f"first:{session_id}:{game_id}:bad",
                ),
                InlineKeyboardButton(
                    text="🙂 Хорошо",
                    callback_data=f"first:{session_id}:{game_id}:good",
                ),
                InlineKeyboardButton(
                    text="😍 Отлично",
                    callback_data=f"first:{session_id}:{game_id}:excellent",
                ),
            ]
        ]
    )


def _second_tier_keyboard(session_id: int, game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🤩 Супер круто",
                    callback_data=f"second:{session_id}:{game_id}:super_cool",
                ),
                InlineKeyboardButton(
                    text="😎 Круто",
                    callback_data=f"second:{session_id}:{game_id}:cool",
                ),
                InlineKeyboardButton(
                    text="🙂 Отлично",
                    callback_data=f"second:{session_id}:{game_id}:excellent",
                ),
            ]
        ]
    )


async def _send_first_tier_question(
    message: Message,
    api_base_url: str,
    user_name: str,
) -> None:
    logger.info(f"Starting ranking for user: {user_name}")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{api_base_url}/api/ranking/start",
                json={"user_name": user_name},
                timeout=30.0,
            )
            resp.raise_for_status()

        data = resp.json()
        session_id = data["session_id"]
        game = data["game"]
        logger.info(f"Ranking session started: session_id={session_id}, first_game={game['name']}")

        usersrated = game.get("usersrated")
        usersrated_text = f" (👥 {usersrated})" if usersrated else ""
        text = (
            f"Начинаем формировать твой рейтинг!\n\n"
            f"Игра: <b>{game['name']}</b>{usersrated_text}\n"
            f"Отметь, насколько она тебе понравилась."
        )
        thumbnail = game.get("thumbnail")
        if thumbnail:
            await message.answer_photo(
                photo=thumbnail,
                caption=text,
                reply_markup=_first_tier_keyboard(session_id=session_id, game_id=game["id"]),
            )
        else:
            await message.answer(
                text,
                reply_markup=_first_tier_keyboard(session_id=session_id, game_id=game["id"]),
            )
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error starting ranking for {user_name}: {e.response.status_code}")
        raise
    except Exception as e:
        logger.error(f"Error starting ranking for {user_name}: {e}", exc_info=True)
        raise


@router.message(Command("start_ranking"))
async def cmd_start_ranking(message: Message, state: FSMContext):
    api_base_url = message.bot["api_base_url"]
    user_name = message.from_user.full_name or str(message.from_user.id)
    user_id = message.from_user.id
    
    logger.info(f"User {user_name} (ID: {user_id}) requested ranking start")
    
    try:
        await _send_first_tier_question(message, api_base_url, user_name)
        await state.set_state(RankingStates.first_tier)
        logger.debug(f"Ranking state set to first_tier for user {user_name}")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to start ranking for user {user_name}: {exc}", exc_info=True)
        await message.answer(f"Не удалось начать ранжирование: {exc}")


@router.callback_query(RankingStates.first_tier)
async def handle_first_tier_callback(callback: CallbackQuery, state: FSMContext, api_base_url: str):
    """
    Обрабатывает callback-данные для первого этапа ранжирования.
    """
    data = callback.data or ""
    user_id = callback.from_user.id

    try:
        kind, session_id_str, game_id_str, tier = data.split(":", 3)
        session_id = int(session_id_str)
        game_id = int(game_id_str)
        logger.debug(f"First tier callback: user_id={user_id}, session_id={session_id}, game_id={game_id}, tier={tier}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Invalid callback data format: {data}, error: {e}")
        await callback.answer("Некорректные данные.", show_alert=True)
        return

    # Проверяем, что это callback первого этапа
    if kind != "first":
        logger.warning(f"Invalid callback kind for first tier: {kind}")
        await callback.answer("Некорректный тип действия для текущего этапа.", show_alert=True)
        return

    await callback.answer()

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{api_base_url}/api/ranking/answer-first",
                json={
                    "session_id": session_id,
                    "game_id": game_id,
                    "tier": tier,
                },
                timeout=30.0,
            )
            resp.raise_for_status()

        payload = resp.json()
        logger.debug(f"First tier answer processed: session_id={session_id}, phase={payload.get('phase')}")
        await _handle_phase_transition(callback, state, payload, session_id)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error processing first tier answer: {e.response.status_code}")
        await callback.message.answer(f"Ошибка при обновлении рейтинга: {e.response.status_code}")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error processing first tier callback: {exc}", exc_info=True)
        await callback.message.answer(f"Ошибка при обновлении рейтинга: {exc}")


@router.callback_query(RankingStates.second_tier)
async def handle_second_tier_callback(callback: CallbackQuery, state: FSMContext, api_base_url: str):
    """
    Обрабатывает callback-данные для второго этапа ранжирования.
    """
    data = callback.data or ""
    user_id = callback.from_user.id

    try:
        kind, session_id_str, game_id_str, tier = data.split(":", 3)
        session_id = int(session_id_str)
        game_id = int(game_id_str)
        logger.debug(f"Second tier callback: user_id={user_id}, session_id={session_id}, game_id={game_id}, tier={tier}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Invalid callback data format: {data}, error: {e}")
        await callback.answer("Некорректные данные.", show_alert=True)
        return

    # Проверяем, что это callback второго этапа
    if kind != "second":
        logger.warning(f"Invalid callback kind for second tier: {kind}")
        await callback.answer("Некорректный тип действия для текущего этапа.", show_alert=True)
        return

    await callback.answer()

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{api_base_url}/api/ranking/answer-second",
                json={
                    "session_id": session_id,
                    "game_id": game_id,
                    "tier": tier,
                },
                timeout=30.0,
            )
            resp.raise_for_status()

        payload = resp.json()
        logger.debug(f"Second tier answer processed: session_id={session_id}, phase={payload.get('phase')}")
        await _handle_phase_transition(callback, state, payload, session_id)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error processing second tier answer: {e.response.status_code}")
        await callback.message.answer(f"Ошибка при обновлении рейтинга: {e.response.status_code}")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error processing second tier callback: {exc}", exc_info=True)
        await callback.message.answer(f"Ошибка при обновлении рейтинга: {exc}")


@router.callback_query(RankingStates.final)
async def handle_final_callback(callback: CallbackQuery, state: FSMContext, api_base_url: str):
    """
    Обрабатывает callback-данные в состоянии final (результаты готовы).
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Начать заново",
                    callback_data="restart_ranking",
                )
            ]
        ]
    )

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer("Хотите начать новое ранжирование?", show_alert=True)


@router.callback_query(RankingStates.completed)
async def handle_completed_callback(callback: CallbackQuery, state: FSMContext, api_base_url: str):
    """
    Обрабатывает callback-данные в состоянии completed (ранжирование окончено).
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Начать заново",
                    callback_data="restart_ranking",
                )
            ]
        ]
    )

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer("Хотите начать новое ранжирование?", show_alert=True)


@router.callback_query()
async def handle_restart_ranking(callback: CallbackQuery, state: FSMContext, api_base_url: str):
    """
    Обрабатывает запрос на перезапуск ранжирования.
    """
    data = callback.data or ""

    if data != "restart_ranking":
        return

    await callback.answer()

    # Сбрасываем состояние
    await state.clear()

    # Начинаем новое ранжирование
    user_name = callback.from_user.full_name or str(callback.from_user.id)

    try:
        await _send_first_tier_question(callback.message, api_base_url, user_name)
        await state.set_state(RankingStates.first_tier)
    except Exception as exc:  # noqa: BLE001
        await callback.message.answer(f"Не удалось начать ранжирование: {exc}")


