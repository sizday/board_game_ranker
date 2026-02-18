FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Копируем весь backend (включая alembic и конфиг) внутрь контейнера
COPY backend/ /app/

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

# Делаем скрипт запуска исполняемым (он уже скопирован через COPY backend/)
RUN chmod +x /app/start.sh

# На Windows файлы могут попасть в образ с CRLF. Нормализуем, чтобы /bin/sh не искал /bin/sh\r
RUN sed -i 's/\r$//' /app/start.sh

EXPOSE 8000

# Используем скрипт запуска, который ждёт готовности БД
CMD ["sh", "/app/start.sh"]


