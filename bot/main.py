import asyncio
import logging
import sys

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

# Настройка логирования
log_level = logging.DEBUG if config.DEBUG else getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

# Настройка уровней для внешних библиотек
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

async def api_base_url_middleware(
    handler,
    event,
    data: Dict[str, Any]
) -> Any:
    """Middleware для передачи API_BASE_URL в handlers."""
    data["api_base_url"] = config.API_BASE_URL
    return await handler(event, data)


async def on_start(message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name or str(user_id)
    logger.info(f"User {user_name} (ID: {user_id}) started bot")
    
    commands = [
        "/start_ranking — начать формирование рейтинга"
    ]

    # Добавляем команду импорта только для админа
    if config.is_admin(message.from_user.id):
        commands.insert(0, "/import_ratings — загрузить данные из Google-таблицы")
        logger.debug(f"Admin commands shown to user {user_name}")

    await message.answer(
        "Привет! Я помогу составить топ-50 твоих настольных игр.\n"
        "Команды:\n" + "\n".join(commands)
    )


async def on_import_ratings(message: Message):
    """
    Команда для импорта данных из Google-таблицы в БД через backend API.
    Доступна только админу.
    """
    user_id = message.from_user.id
    user_name = message.from_user.full_name or str(user_id)
    
    # Проверка прав доступа
    if not config.is_admin(message.from_user.id):
        logger.warning(f"Non-admin user {user_name} (ID: {user_id}) attempted to import ratings")
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    logger.info(f"Admin {user_name} (ID: {user_id}) started ratings import")
    await message.answer("Начинаю загрузку данных из Google-таблицы...")

    try:
        imported_count = await import_ratings_from_sheet(
            api_base_url=config.API_BASE_URL,
            sheet_csv_url=config.RATING_SHEET_CSV_URL,
        )
        if imported_count == 0:
            logger.warning("Import completed but no games were imported")
            await message.answer("Таблица пуста, нечего импортировать.")
        else:
            logger.info(f"Import completed successfully: {imported_count} games imported")
            await message.answer(
                f"Импорт данных в БД успешно завершен. Импортировано игр: {imported_count}."
            )
    except ValueError as exc:
        logger.error(f"Validation error during import: {exc}")
        await message.answer(str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error during ratings import: {exc}", exc_info=True)
        await message.answer(f"Ошибка при импорте данных: {exc}")


async def main():
    logger.info("Starting bot...")
    
    # Валидация конфигурации
    try:
        config.validate()
        logger.info("Configuration validated successfully")
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    logger.info("Bot instance created")

    dp = Dispatcher()
    dp.update.middleware(api_base_url_middleware)
    logger.debug("Middleware registered")

    # Команды верхнего уровня
    dp.message.register(on_start, CommandStart())
    dp.message.register(on_import_ratings, Command("import_ratings"))
    logger.debug("Commands registered")

    # Подключаем роутеры
    dp.include_router(ranking_router)
    dp.include_router(bgg_game_router)
    logger.info("Routers included")

    logger.info("Starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


