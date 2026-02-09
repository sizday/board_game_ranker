# Board Game Ranker

Приложение для ранжирования настольных игр через Telegram бота.

## Запуск через Docker Compose

### 1. Клонируйте репозиторий

```bash
git clone <repository-url>
cd board-game-ranker
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

### 2.2. Настройте Google Sheets

1. Создайте Google таблицу с данными о играх
2. Опубликуйте таблицу: **Файл → Поделиться → Опубликовать в интернете**
3. Выберите формат CSV и скопируйте ссылку на экспорт

### 2.3. Заполните переменные окружения

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

# Или с миграциями базы данных
docker-compose --profile migrate up -d
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

### Переменные окружения
Все параметры можно переопределить через `.env` файл. Смотрите `env.example` для полного списка доступных переменных.

## Команды бота

- `/start` - начать работу с ботом
- `/import_ratings` - загрузить данные из Google таблицы (только для админа)
- `/start_ranking` - начать процесс ранжирования игр

## Импорт данных

Данные импортируются из Google Sheets. Формат таблицы:
- Колонка A: Название игры
- Колонка B: Жанр (стратегия, семейка, патигейм, кооп, амери, евро, абстракт)
- Колонка C: Рейтинг BGG
- Колонка D: Рейтинг Niza Games
- Остальные колонки: рейтинги пользователей (числа от 1 до 10)

## Конфигурационные файлы

- `env.example` - пример файла с переменными окружения
- `backend/app/config.py` - конфигурация backend (база данных, сервер)
- `bot/config.py` - конфигурация бота (токены, URLs, timeouts)

## Разработка

### Локальный запуск backend

```bash
cd backend
pip install -r requirements-backend.txt
# Установите переменные окружения или создайте .env файл
export DATABASE_URL="postgresql+psycopg2://board_user:board_password@localhost:5432/board_games"
python wsgi.py
```

### Локальный запуск бота

```bash
cd bot
pip install -r requirements-bot.txt
# Установите переменные окружения
export BOT_TOKEN="your_bot_token"
export RATING_SHEET_CSV_URL="your_csv_url"
python main.py
```
