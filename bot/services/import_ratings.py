import csv
import io
import logging
import time
from typing import List, Dict, Optional, Callable

import httpx

logger = logging.getLogger(__name__)


# Маппинг русских названий жанров на английские enum значения
GENRE_MAPPING = {
    "стратегия": "strategy",
    "семейка": "family",
    "патигейм": "party",
    "кооп": "coop",
    "амери": "ameri",
    "евро": "euro",
    "абстракт": "abstract",
}


async def _wait_for_backend(api_base_url: str, max_attempts: int = 30, delay: float = 2.0) -> None:
    """Ожидает готовности backend API."""
    health_url = f"{api_base_url}/health"
    logger.info(f"Waiting for backend to be ready: {health_url}")

    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(health_url)
                if resp.status_code == 200:
                    logger.info(f"Backend is ready after {attempt + 1} attempts")
                    return
        except Exception as e:
            logger.debug(f"Backend not ready yet (attempt {attempt + 1}/{max_attempts}): {e}")

        if attempt < max_attempts - 1:
            time.sleep(delay)

    logger.error(f"Backend did not become available after {max_attempts} attempts")
    raise RuntimeError(f"Backend не стал доступен после {max_attempts} попыток")


def _parse_int_or_none(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


async def import_ratings_from_sheet(
    api_base_url: str,
    sheet_csv_url: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> int:
    """
    Загружает CSV из Google-таблицы, парсит её и отправляет данные в backend API.

    Возвращает количество импортированных игр.
    Может возбуждать ValueError при проблемах с форматом данных.
    """
    logger.info(f"Starting import from sheet: {sheet_csv_url}")
    
    if not sheet_csv_url:
        logger.error("RATING_SHEET_CSV_URL not configured")
        raise ValueError(
            "Переменная окружения RATING_SHEET_CSV_URL не задана. "
            "Укажи ссылку на CSV Google-таблицы в конфигурации бота."
        )

    # Ожидаем готовности backend
    await _wait_for_backend(api_base_url)

    logger.info("Downloading CSV from Google Sheets...")
    async with httpx.AsyncClient() as client:
        resp = await client.get(sheet_csv_url, follow_redirects=True)
        resp.raise_for_status()

    text = resp.text
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    logger.info(f"CSV downloaded: {len(rows)} rows")

    if not rows:
        logger.error("CSV file is empty")
        raise ValueError("CSV файл пустой или недоступен")

    # Проверяем минимальный формат
    if len(rows) < 2:  # Минимум заголовок + одна строка данных
        logger.error(f"CSV file has insufficient rows: {len(rows)}")
        raise ValueError(f"CSV файл содержит только {len(rows)} строк. Минимум требуется заголовок + одна строка данных")

    header = rows[0]
    if len(header) < 5:
        logger.error(f"CSV header has insufficient columns: {len(header)}, header: {header}")
        raise ValueError(f"Недостаточно колонок в заголовке. Ожидается минимум 5, получено {len(header)}. Заголовок: {header}")

    return await _process_sheet_data(api_base_url, rows, progress_callback)


async def _process_sheet_data(api_base_url: str, rows: List[List[str]], progress_callback: Optional[Callable[[int, int, str], None]] = None) -> int:
    """Обрабатывает данные листа и отправляет в backend"""
    logger.info(f"Processing sheet data: {len(rows)} rows")
    
    if not rows:
        logger.warning("No rows to process")
        return 0

    header = rows[0]
    if len(header) < 5:
        logger.error(f"Unexpected table format: expected at least 5 columns, got {len(header)}")
        raise ValueError("Неожиданный формат таблицы: ожидается минимум 5 колонок.")

    # Фактический формат таблицы согласно диагностике:
    # 0: название игры
    # 1: жанр
    # 2: bgg (рейтинг BGG)
    # 3: НизаГамс (рейтинг Niza Games)
    # 4..N: имена пользователей (столбцы рейтингов)
    user_names: List[str] = [h.strip() for h in header[4:] if h.strip()]
    logger.info(f"Found {len(user_names)} users in sheet: {user_names}")

    data_rows: List[Dict] = []
    skipped_rows = 0
    
    for row_idx, row in enumerate(rows[1:], start=2):
        # пропустим полностью пустые строки
        if not any(cell.strip() for cell in row):
            skipped_rows += 1
            continue

        name = (row[0] or "").strip() if len(row) > 0 else ""
        if not name:
            skipped_rows += 1
            continue

        # Исправленный порядок согласно таблице:
        # row[0] = название игры
        # row[1] = жанр
        # row[2] = bgg (рейтинг BGG)
        # row[3] = НизаГамс (рейтинг Niza Games)
        genre_raw = (row[1] or "").strip().lower() if len(row) > 1 else None
        genre = GENRE_MAPPING.get(genre_raw, genre_raw) if genre_raw else None
        bgg_rank = _parse_int_or_none(row[2]) if len(row) > 2 else None
        niza_rank = _parse_int_or_none(row[3]) if len(row) > 3 else None

        ratings: Dict[str, int] = {}
        for idx, user_name in enumerate(user_names, start=4):
            if idx >= len(row):
                continue
            cell = (row[idx] or "").strip()
            if not cell or cell.lower() == "нет":
                continue
            try:
                ratings[user_name] = int(cell)
            except ValueError:
                # игнорируем некорректные значения
                logger.debug(f"Invalid rating value in row {row_idx}, column {idx}: {cell}")
                continue

        data_rows.append(
            {
                "name": name,
                "bgg_rank": bgg_rank,
                "niza_games_rank": niza_rank,
                "genre": genre or None,
                "ratings": ratings,
            }
        )

    logger.info(f"Processed {len(data_rows)} games, skipped {skipped_rows} rows")

    # Отправляем данные в backend с повторными попытками
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Sending data to backend (attempt {attempt + 1}/{max_retries})...")
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{api_base_url}/api/import-table",
                    json={"rows": data_rows},
                    timeout=120.0,  # Увеличиваем таймаут для импорта
                )
                resp.raise_for_status()
            logger.info(f"Successfully sent data to backend on attempt {attempt + 1}")
            break  # Успешно отправили данные
        except Exception as e:
            logger.warning(f"Failed to send data to backend (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to send data after {max_retries} attempts")
                raise RuntimeError(f"Не удалось отправить данные в backend после {max_retries} попыток: {e}")
            time.sleep(2 ** attempt)  # Экспоненциальная задержка

    return len(data_rows)


