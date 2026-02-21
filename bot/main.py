import asyncio
import logging
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from typing import Dict, Any

from handlers.ranking import router as ranking_router
from handlers.bgg_game import router as bgg_game_router
from handlers.login import router as login_router
from handlers.my_games import router as my_games_router
from services.import_ratings import import_ratings_from_sheet
from services.clear_database import clear_database
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


async def default_language_middleware(
    handler,
    event,
    data: Dict[str, Any]
) -> Any:
    """Middleware для передачи DEFAULT_LANGUAGE в handlers."""
    data["default_language"] = config.DEFAULT_LANGUAGE
    return await handler(event, data)


async def on_start(message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name or str(user_id)
    logger.info(f"User {user_name} (ID: {user_id}) started bot")
    
    commands = [
        "/login — зарегистрироваться в системе",
        "/my_games — посмотреть свои игры",
        "/start_ranking — начать формирование рейтинга"
    ]

    # Добавляем команды админа
    if config.is_admin(message.from_user.id):
        commands.insert(0, "/import — загрузить данные из Google-таблицы")
        commands.insert(0, "/clear — очистить всю базу данных")
        logger.debug(f"Admin commands shown to user {user_name}")

    await message.answer(
        "Привет! Я помогу составить топ-50 твоих настольных игр.\n"
        "Команды:\n" + "\n".join(commands)
    )


async def on_import(message: Message):
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

    # Отправляем начальное сообщение
    await message.answer("🚀 Начинаю импорт данных из Google Sheets...")

    try:
        imported_count = await import_ratings_from_sheet(
            api_base_url=config.API_BASE_URL,
            sheet_csv_url=config.RATING_SHEET_CSV_URL,
        )

        if imported_count == 0:
            logger.warning("Import completed but no games were imported")
            await message.answer("⚠️ Таблица пуста или данные не найдены.")
        else:
            logger.info(f"Import completed successfully: {imported_count} games imported")
            await message.answer(
                f"✅ Импорт завершен!\n\n"
                f"Загружено данных для {imported_count} игр.\n"
                f"Игры добавляются в базу данных по одной с автоматической загрузкой данных из BGG."
            )
    except ValueError as exc:
        logger.error(f"Validation error during import: {exc}")
        await message.answer(str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error during ratings import: {exc}", exc_info=True)
        await message.answer(f"Ошибка при импорте данных: {exc}")


async def on_clear_database(message: Message):
    """
    Команда для очистки всей базы данных через backend API.
    Доступна только админу.
    """
    user_id = message.from_user.id
    user_name = message.from_user.full_name or str(user_id)

    # Проверка прав доступа
    if not config.is_admin(message.from_user.id):
        logger.warning(f"Non-admin user {user_name} (ID: {user_id}) attempted to clear database")
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    logger.info(f"Admin {user_name} (ID: {user_id}) started database clear")

    try:
        result = await clear_database(api_base_url=config.API_BASE_URL)

        games_deleted = result.get("games_deleted", 0)
        ratings_deleted = result.get("ratings_deleted", 0)
        sessions_deleted = result.get("sessions_deleted", 0)
        users_deleted = result.get("users_deleted", 0)

        logger.info(f"Database cleared successfully by admin {user_name}: games={games_deleted}, ratings={ratings_deleted}, sessions={sessions_deleted}, users={users_deleted}")

        await message.answer(
            "✅ База данных успешно очищена!\n\n"
            f"Удалено:\n"
            f"• Игр: {games_deleted}\n"
            f"• Рейтингов: {ratings_deleted}\n"
            f"• Сессий ранжирования: {sessions_deleted}\n"
            f"• Пользователей: {users_deleted}"
        )

    except RuntimeError as exc:
        logger.error(f"Runtime error during database clear: {exc}")
        await message.answer(f"❌ Ошибка при очистке базы данных: {exc}")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Unexpected error during database clear: {exc}", exc_info=True)
        await message.answer(f"❌ Неожиданная ошибка при очистке базы данных: {exc}")


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
    dp.update.middleware(default_language_middleware)
    logger.debug("Middleware registered")

    # Команды верхнего уровня
    dp.message.register(on_start, CommandStart())
    dp.message.register(on_import, Command("import"))
    dp.message.register(on_clear_database, Command("clear"))
    logger.debug("Commands registered")

    # Подключаем роутеры
    dp.include_router(ranking_router)
    dp.include_router(bgg_game_router)
    dp.include_router(login_router)
    dp.include_router(my_games_router)
    logger.info("Routers included")

    logger.info("Starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


