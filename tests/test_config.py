#!/usr/bin/env python3
"""
Скрипт для тестирования конфигурации приложения
"""
import os
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_backend_config():
    """Тестирование backend конфигурации"""
    print("🔧 Тестирование backend конфигурации...")

    try:
        sys.path.insert(0, str(project_root / 'backend'))
        from app.config import config

        print("✅ Backend config загружен")
        print(f"   DATABASE_URL: {config.DATABASE_URL}")
        print(f"   DB_HOST: {config.DB_HOST}")
        print(f"   DB_USER: {config.DB_USER}")
        print(f"   FLASK_ENV: {config.FLASK_ENV}")
        print(f"   DEBUG: {config.DEBUG}")

        return True
    except Exception as e:
        print(f"❌ Ошибка backend config: {e}")
        return False

def test_bot_config():
    """Тестирование bot конфигурации"""
    print("\n🤖 Тестирование bot конфигурации...")

    try:
        sys.path.insert(0, str(project_root / 'bot'))
        from config import config

        print("✅ Bot config загружен")
        print(f"   BOT_TOKEN: {'***' + config.BOT_TOKEN[-4:] if config.BOT_TOKEN else 'не задан'}")
        print(f"   ADMIN_USER_ID: {config.ADMIN_USER_ID}")
        print(f"   API_BASE_URL: {config.API_BASE_URL}")
        print(f"   RATING_SHEET_CSV_URL: {'***' if config.RATING_SHEET_CSV_URL else 'не задан'}")
        print(f"   DB_HOST: {config.DB_HOST}")
        print(f"   DATABASE_URL: {config.DATABASE_URL}")

        # Валидация
        try:
            config.validate()
            print("✅ Конфигурация прошла валидацию")
        except ValueError as e:
            print(f"⚠️  Валидация: {e}")

        return True
    except Exception as e:
        print(f"❌ Ошибка bot config: {e}")
        return False

def main():
    print("🚀 Тестирование конфигурации Board Game Ranker")
    print("=" * 50)

    backend_ok = test_backend_config()
    bot_ok = test_bot_config()

    print("\n" + "=" * 50)
    if backend_ok and bot_ok:
        print("🎉 Все конфигурации загружены успешно!")
    else:
        print("❌ Есть проблемы с конфигурацией")

    print("\n💡 Советы:")
    print("- Создайте .env файл на основе env.example")
    print("- Установите BOT_TOKEN и RATING_SHEET_CSV_URL")
    print("- Проверьте DATABASE_URL для вашей среды")

if __name__ == "__main__":
    main()
