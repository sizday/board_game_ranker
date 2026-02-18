# Board Game Ranker

Приложение для ранжирования настольных игр через Telegram бота.

## Запуск через Docker Compose

### 1. Клонируйте репозиторий

```bash
git clone <repository-url>
cd board_game_ranker
```

### 2. Создайте файл с переменными окружения

```bash
cp env.example .env
```

### 2.1. Получите токен Telegram бота

1. Напишите [@BotFather](https://t.me/botfather) в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям для создания бота
4. Скопируйте токен (начинается с числа, например: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### 2.2. Получите ваш Telegram User ID

1. Напишите [@userinfobot](https://t.me/userinfobot) в Telegram
2. Отправьте любое сообщение
3. Бот ответит вашим User ID (число, например: `123456789`)

### 2.3. Настройте Google Sheets

1. Создайте Google таблицу с данными о играх
2. Опубликуйте таблицу: **Файл → Поделиться → Опубликовать в интернете**
3. Выберите формат CSV и скопируйте ссылку на экспорт

### 2.4. Заполните переменные окружения

Заполните `.env` файл:
- `BOT_TOKEN` - токен от BotFather (обязательно)
- `ADMIN_USER_ID` - ваш Telegram User ID от @userinfobot (обязательно)
- `RATING_SHEET_CSV_URL` - ссылка на CSV экспорт таблицы (обязательно)
- `DATABASE_URL` - строка подключения к PostgreSQL (уже настроена для Docker)
- `API_BASE_URL` - URL backend API (уже настроен для Docker)
- `APP_ENV` - среда выполнения (development/production/testing)

**Безопасность:** `BOT_TOKEN` хранится только в `.env` файле, не в `docker-compose.yml`.

### 3. Запустите приложение

```bash
# Полный запуск всех сервисов
docker-compose up -d
```

### 4. Проверьте статус

```bash
docker-compose ps
```

### 5. Проверьте логи (опционально)

```bash
# Логи всех сервисов
docker-compose logs

# Логи конкретного сервиса
docker-compose logs backend
docker-compose logs bot
```

### 5. Остановите приложение

```bash
docker-compose down
```

## Архитектура

- **Backend** (FastAPI) - API сервер на порту 8000
- **Bot** (aiogram) - Telegram бот для взаимодействия с пользователями
- **Database** (PostgreSQL) - база данных на порту 5432

## Конфигурация

Приложение использует централизованную систему конфигурации:

### Backend конфигурация (`backend/app/config.py`)
- Настройки базы данных
- Параметры сервера
- Режим работы (development/production/testing)

### Bot конфигурация (`bot/config.py`)
- Telegram Bot токен
- URLs для API и Google Sheets
- Параметры подключения к БД
- Настройки webhook/polling
- Язык отображения описаний игр (`DEFAULT_LANGUAGE`)

### Переменные окружения
Все параметры можно переопределить через `.env` файл. Смотрите `env.example` для полного списка доступных переменных.

#### Ключевые переменные для перевода:
- `DEFAULT_LANGUAGE=ru` - язык отображения описаний игр ("ru" для русского, "en" для английского)
- При установке `ru` бот будет пытаться показать переведенное описание, если оно доступно

## Команды бота

### Telegram бот: команды и использование

Бот работает в Telegram и общается с backend через `API_BASE_URL` (см. `.env`).

#### Основные команды

- `/start` — показать краткую справку по доступным командам.

- `/start_ranking` — начать процесс ранжирования (бот будет задавать вопросы и собирать ваш топ).
  - Ответы выбираются кнопками в чате.
  - В конце бот покажет итоговый список.

- `/game <название>` — найти настольную игру и показать полную информацию.
  - Сначала ищет в локальной базе данных, затем на BoardGameGeek
  - Автоматически сохраняет найденные игры в базу данных для быстрого доступа в будущем
  - Поддерживает отображение описаний на русском или английском языке (настраивается через `DEFAULT_LANGUAGE`)
  - Примеры:
    - `/game Terraforming Mars`
    - `/game Root`

#### Команды администратора

- `/import_ratings` — импортировать данные из Google Sheets в БД через backend API (только для админа).
  - Требует переменных окружения: `RATING_SHEET_CSV_URL`, `ADMIN_USER_ID`.
  - Обычно используется после обновления таблицы.

#### Частые проблемы

- Если `/game` или импорт не работают, проверьте:
  - `API_BASE_URL` (в Docker обычно `http://backend:8000`)
  - `BGG_BEARER_TOKEN` (для запросов к BGG)
  - логи: `docker-compose logs bot` и `docker-compose logs backend`

#### Логирование BGG запросов

Все запросы к BGG API логируются с подробной информацией:
- **INFO** — успешные запросы, найденные игры, количество результатов
- **WARNING** — пустые ответы, отсутствие результатов поиска
- **ERROR** — ошибки HTTP запросов, проблемы с парсингом XML, отсутствие токена

Для просмотра логов BGG запросов:
```bash
# Все логи backend
docker-compose logs backend

# Только логи BGG (фильтрация)
docker-compose logs backend | grep -i bgg

# Логи в реальном времени
docker-compose logs -f backend | grep -i bgg
```

Примеры логов при успешном поиске:
```
INFO - Поиск игры на BGG: query='Terraforming Mars', exact=False
INFO - BGG search успешен: найдено 3 игр для запроса 'Terraforming Mars'
INFO - Запрос деталей игры с BGG: game_id=167791
INFO - BGG thing успешен для game_id=167791: name='Terraforming Mars', rank=4
```

Примеры логов при ошибках:
```
ERROR - BGG_BEARER_TOKEN не задан в конфигурации
WARNING - BGG вернул пустой ответ для запроса 'NonExistentGame'
ERROR - Ошибка HTTP запроса к BGG (попытка 1/3): Connection timeout
```

## Импорт данных

### Ручной импорт из Google Sheets
Данные импортируются из Google Sheets по команде `/import_ratings`. Формат таблицы:
- Колонка A: Название игры
- Колонка B: Жанр (стратегия, семейка, патигейм, кооп, амери, евро, абстракт)
- Колонка C: Рейтинг BGG
- Колонка D: Рейтинг Niza Games
- Остальные колонки: рейтинги пользователей (числа от 1 до 10)

### Автоматическое сохранение игр
При использовании команды `/game` бот автоматически сохраняет найденные игры в базу данных для быстрого доступа в будущем. Это включает:
- Полную информацию об игре из BGG
- Фоновый перевод описания на русский язык (если `DEFAULT_LANGUAGE=ru`)
- Кеширование для снижения нагрузки на BGG API

## Конфигурационные файлы

- `env.example` - пример файла с переменными окружения
- `backend/app/config.py` - конфигурация backend (база данных, сервер)
- `bot/config.py` - конфигурация бота (токены, URLs, timeouts)

## Тестирование

### Запуск тестов

```bash
# Запуск всех тестов
python tests/run_tests.py

# Или запуск отдельных типов тестов
python -m pytest tests/ -v

# Запуск тестов конфигурации
python tests/test_config.py

# Запуск тестов администратора
python tests/test_admin.py

# Запуск тестов импорта
python tests/test_import.py
```

### Структура тестов

- `tests/test_translation_service.py` - тесты сервиса перевода
- `tests/test_repositories.py` - тесты функций репозитория
- `tests/test_api_games.py` - тесты API endpoints для игр
- `tests/test_bot_handlers.py` - тесты обработчиков бота
- `tests/test_config.py` - тесты конфигурации
- `tests/test_admin.py` - тесты функционала админа
- `tests/test_import.py` - тесты импорта данных

## Разработка

### Локальный запуск backend

```bash
cd backend
pip install -r requirements-backend.txt
# Установите переменные окружения или создайте .env файл
# Linux/macOS:
# export DATABASE_URL="postgresql+psycopg2://board_user:board_password@localhost:5432/board_games"
# Windows PowerShell:
# $env:DATABASE_URL="postgresql+psycopg2://board_user:board_password@localhost:5432/board_games"
python wsgi.py
```

### Локальный запуск бота

```bash
cd bot
pip install -r requirements-bot.txt
# Установите переменные окружения
# Linux/macOS:
# export BOT_TOKEN="your_bot_token"
# export RATING_SHEET_CSV_URL="your_csv_url"
# Windows PowerShell:
# $env:BOT_TOKEN="your_bot_token"
# $env:RATING_SHEET_CSV_URL="your_csv_url"
python main.py
```
