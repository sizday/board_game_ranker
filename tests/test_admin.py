#!/usr/bin/env python3
"""
Тест функционала админа для бота
"""
import sys
import os
from pathlib import Path

# Добавляем корень проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_admin_functionality():
    """Тестирование функционала админа"""
    print("🛡️  Тестирование функционала админа...")

    try:
        sys.path.insert(0, str(project_root / 'bot'))
        from config import config

        print("✅ Конфигурация бота загружена")

        # Тест наличия ADMIN_USER_ID
        if config.ADMIN_USER_ID:
            print(f"✅ ADMIN_USER_ID установлен: {config.ADMIN_USER_ID}")

            # Тест метода is_admin
            admin_id = config.ADMIN_USER_ID
            test_user_id = 999999999

            print(f"   Проверка админа (ID: {admin_id}): {config.is_admin(admin_id)}")
            print(f"   Проверка обычного пользователя (ID: {test_user_id}): {config.is_admin(test_user_id)}")

            # Проверка типов
            assert isinstance(config.is_admin(admin_id), bool), "is_admin должен возвращать bool"
            assert config.is_admin(admin_id) == True, "Админ должен быть распознан"
            assert config.is_admin(test_user_id) == False, "Обычный пользователь не должен быть админом"

            print("✅ Метод is_admin работает корректно")
            return True
        else:
            print("❌ ADMIN_USER_ID не установлен")
            return False

    except Exception as e:
        print(f"❌ Ошибка тестирования админа: {e}")
        return False


def main():
    print("🚀 Тестирование функционала админа")
    print("=" * 50)

    admin_ok = test_admin_functionality()

    print("\n" + "=" * 50)
    if admin_ok:
        print("🎉 Функционал админа работает корректно!")
        print("\n💡 Как использовать:")
        print("- Установите ADMIN_USER_ID в .env файл")
        print("- Только пользователь с этим ID сможет использовать /import_ratings")
        print("- Другие пользователи увидят сообщение об отсутствии прав")
    else:
        print("❌ Проблемы с функционалом админа")
        print("Установите ADMIN_USER_ID в переменных окружения")


if __name__ == "__main__":
    main()
