"""
Тесты для Board Game Ranker
"""
import os
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Устанавливаем переменную окружения для тестирования
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("TESTING", "true")