import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from typing import Dict, Any

from handlers.ranking import router as ranking_router
from handlers.bgg_game import router as bgg_game_router
from services.import_ratings import import_ratings_from_sheet
from config import config

async def api_base_url_middleware(
    handler,
    event,
    data: Dict[str, Any]
) -> Any:
    """Middleware для передачи API_BASE_URL в handlers."""
    data["api_base_url"] = config.API_BASE_URL
    return await handler(event, data)


async def on_start(message: Message):
    commands = [
        "/start_ranking — начать формирование рейтинга"
    ]

    # Добавляем команду импорта только для админа
    if config.is_admin(message.from_user.id):
        commands.insert(0, "/import_ratings — загрузить данные из Google-таблицы")

    await message.answer(
        "Привет! Я помогу составить топ-50 твоих настольных игр.\n"
        "Команды:\n" + "\n".join(commands)
    )


async def on_import_ratings(message: Message):
    """
    Команда для импорта данных из Google-таблицы в БД через backend API.
    Доступна только админу.
    """
    # Проверка прав доступа
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    await message.answer("Начинаю загрузку данных из Google-таблицы...")

    try:
        imported_count = await import_ratings_from_sheet(
            api_base_url=config.API_BASE_URL,
            sheet_csv_url=config.RATING_SHEET_CSV_URL,
        )
        if imported_count == 0:
            await message.answer("Таблица пуста, нечего импортировать.")
        else:
            await message.answer(
                f"Импорт данных в БД успешно завершен. Импортировано игр: {imported_count}."
            )
    except ValueError as exc:
        await message.answer(str(exc))
    except Exception as exc:  # noqa: BLE001
        await message.answer(f"Ошибка при импорте данных: {exc}")


async def main():
    # Валидация конфигурации
    config.validate()

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    dp = Dispatcher()
    dp.update.middleware(api_base_url_middleware)

    # Команды верхнего уровня
    dp.message.register(on_start, CommandStart())
    dp.message.register(on_import_ratings, Command("import_ratings"))

    # Подключаем роутеры
    dp.include_router(ranking_router)
    dp.include_router(bgg_game_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


