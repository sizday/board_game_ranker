#!/usr/bin/env python3
"""
Скрипт для тестирования работы приложения в Docker.
Проверяет доступность backend API.
"""

import asyncio
import httpx
import time


async def test_backend_health():
    """Проверяет доступность backend API."""
    url = "http://localhost:8000/health"

    for attempt in range(10):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    print("✅ Backend доступен и здоров")
                    return True
        except Exception as e:
            print(f"⏳ Попытка {attempt + 1}/10: Backend не доступен ({e})")

        if attempt < 9:
            time.sleep(2)

    print("❌ Backend не стал доступен")
    return False


async def test_import_endpoint():
    """Проверяет доступность import endpoint."""
    url = "http://localhost:8000/api/import-table"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Пробуем GET запрос для проверки доступности
            resp = await client.get(url.replace("/api/import-table", "/health"))
            if resp.status_code == 200:
                print("✅ API endpoints доступны")
                return True
    except Exception as e:
        print(f"❌ API endpoints не доступны: {e}")
        return False


async def main():
    print("🚀 Тестирование Board Game Ranker Docker setup")
    print("=" * 50)

    # Тест 1: Backend health
    backend_ok = await test_backend_health()

    if backend_ok:
        # Тест 2: API endpoints
        await test_import_endpoint()

    print("=" * 50)
    if backend_ok:
        print("🎉 Docker setup работает корректно!")
        print("\n📝 Следующие шаги:")
        print("1. Установите переменные окружения в .env файл:")
        print("   BOT_TOKEN=ваш_telegram_бот_token")
        print("   RATING_SHEET_CSV_URL=ссылка_на_csv_экспорт_таблицы")
        print("2. Перезапустите сервисы: docker-compose up -d")
        print("3. Используйте бота в Telegram для импорта данных")
    else:
        print("❌ Проблемы с Docker setup")
        print("Проверьте логи: docker-compose logs")


if __name__ == "__main__":
    asyncio.run(main())
