"""
Конфигурация приложения Board Game Ranker Backend
"""
import os
from typing import Optional


class Config:
    """Базовый класс конфигурации"""

    # FastAPI настройки
    APP_ENV: str = os.getenv("APP_ENV", "development")

    # Настройки сервера
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # База данных
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://board_user:board_password@db:5432/board_games"
    )

    # Разбор DATABASE_URL для отдельных компонентов
    @property
    def DB_HOST(self) -> str:
        """Хост базы данных"""
        # Для Docker сети используем service name, для локальной разработки - localhost
        if "db:" in self.DATABASE_URL:
            return "db"
        return "localhost"

    @property
    def DB_PORT(self) -> int:
        """Порт базы данных"""
        return 5432

    @property
    def DB_NAME(self) -> str:
        """Имя базы данных"""
        return "board_games"

    @property
    def DB_USER(self) -> str:
        """Пользователь базы данных"""
        return "board_user"

    @property
    def DB_PASSWORD(self) -> str:
        """Пароль базы данных"""
        return "board_password"

    # Дополнительные настройки
    DEBUG: bool = APP_ENV == "development"
    TESTING: bool = os.getenv("TESTING", "false").lower() == "true"

    # BGG / внешние API
    BGG_BEARER_TOKEN: Optional[str] = os.getenv("BGG_BEARER_TOKEN")

    # Настройки обновления данных игр из BGG
    # Количество дней, после которого данные игры считаются устаревшими
    # и могут быть автоматически обновлены при импорте таблицы.
    GAME_UPDATE_DAYS: int = int(os.getenv("GAME_UPDATE_DAYS", "30"))

    # Задержка между запросами к BGG API в секундах (для избежания rate limiting)
    BGG_REQUEST_DELAY: float = float(os.getenv("BGG_REQUEST_DELAY", "2.0"))

    # Язык по умолчанию для отображения описаний игр
    # "ru" - русский (переведенный), "en" - английский (оригинал)
    DEFAULT_LANGUAGE: str = os.getenv("DEFAULT_LANGUAGE", "ru")


class DevelopmentConfig(Config):
    """Конфигурация для разработки"""
    DEBUG = True
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://board_user:board_password@localhost:5432/board_games"
    )


class ProductionConfig(Config):
    """Конфигурация для продакшена"""
    DEBUG = False
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://board_user:board_password@db:5432/board_games"
    )


class TestingConfig(Config):
    """Конфигурация для тестирования"""
    TESTING = True
    DEBUG = True
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://board_user:board_password@localhost:5432/board_games_test"
    )


# Выбор конфигурации на основе APP_ENV
def get_config() -> Config:
    """Получить текущую конфигурацию на основе переменных окружения"""
    env = os.getenv("APP_ENV", "development")

    if env == "production":
        return ProductionConfig()
    elif env == "testing":
        return TestingConfig()
    else:
        return DevelopmentConfig()


# Глобальный экземпляр конфигурации
config = get_config()
