"""
Конфигурация Telegram бота Board Game Ranker
"""
import os
from typing import Optional


class BotConfig:
    """Конфигурация бота"""

    # Telegram Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # Admin настройки
    ADMIN_USER_ID: Optional[int] = int(os.getenv("ADMIN_USER_ID", "0")) if os.getenv("ADMIN_USER_ID") else None

    # API настройки
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://backend:8000")

    # Google Sheets
    RATING_SHEET_CSV_URL: str = os.getenv("RATING_SHEET_CSV_URL", "")

    # Настройки подключения к БД (для отладки/прямого доступа)
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "board_games")
    DB_USER: str = os.getenv("DB_USER", "board_user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "board_password")

    @property
    def DATABASE_URL(self) -> str:
        """Полная строка подключения к БД"""
        return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Настройки бота
    WEBHOOK_URL: Optional[str] = os.getenv("WEBHOOK_URL")
    WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "/webhook")

    # Режим работы
    POLLING: bool = os.getenv("POLLING", "true").lower() == "true"
    WEBHOOK: bool = os.getenv("WEBHOOK", "false").lower() == "true"

    # Отладка
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Таймауты
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    CONNECT_TIMEOUT: int = int(os.getenv("CONNECT_TIMEOUT", "10"))

    def validate(self) -> None:
        """Валидация обязательных параметров"""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")

        if not self.RATING_SHEET_CSV_URL:
            raise ValueError("RATING_SHEET_CSV_URL is required")

        if not self.ADMIN_USER_ID:
            raise ValueError("ADMIN_USER_ID is required")

    def is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь админом"""
        return self.ADMIN_USER_ID == user_id

    @property
    def is_production(self) -> bool:
        """Проверка на продакшн режим"""
        return self.WEBHOOK and self.WEBHOOK_URL

    @property
    def is_development(self) -> bool:
        """Проверка на режим разработки"""
        return self.POLLING and not self.WEBHOOK


# Глобальный экземпляр конфигурации
config = BotConfig()
