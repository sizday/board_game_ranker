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
cp .env.example .env
```

Заполните `.env` файл:
- `BOT_TOKEN` - токен вашего Telegram бота
- `RATING_SHEET_CSV_URL` - ссылка на CSV экспорт Google таблицы с рейтингами

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

### 5. Остановите приложение

```bash
docker-compose down
```

## Архитектура

- **Backend** (FastAPI) - API сервер на порту 8000
- **Bot** (aiogram) - Telegram бот для взаимодействия с пользователями
- **Database** (PostgreSQL) - база данных на порту 5432

## Команды бота

- `/start` - начать работу с ботом
- `/import_ratings` - загрузить данные из Google таблицы
- `/start_ranking` - начать процесс ранжирования игр

## Импорт данных

Данные импортируются из Google Sheets. Формат таблицы:
- Колонка A: Название игры
- Колонка B: Жанр (стратегия, семейка, патигейм, кооп, амери, евро, абстракт)
- Колонка C: Рейтинг BGG
- Колонка D: Рейтинг Niza Games
- Остальные колонки: рейтинги пользователей (числа от 1 до 10)

## Разработка

### Локальный запуск backend

```bash
cd backend
pip install -r requirements-backend.txt
python wsgi.py
```

### Локальный запуск бота

```bash
cd bot
pip install -r requirements-bot.txt
python main.py
```
