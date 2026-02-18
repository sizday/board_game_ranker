import logging
import time
from typing import List, Dict, Any, Optional

import xml.etree.ElementTree as ET

from app.config import config

logger = logging.getLogger(__name__)

try:
    import requests
except ImportError as exc:  # pragma: no cover - only for local runtime
    raise SystemExit(
        "Для работы модуля BGG требуется библиотека 'requests'. "
        "Установите её командой:\n\n"
        "    pip install requests\n"
    ) from exc


BGG_SEARCH_URL = "https://boardgamegeek.com/xmlapi2/search"
BGG_THING_URL = "https://boardgamegeek.com/xmlapi2/thing"


def _resolve_token(explicit_token: Optional[str] = None) -> str:
    """
    Возвращает Bearer‑токен BGG:
    - сначала берёт явный параметр функции,
    - иначе значение из конфигурации (config.BGG_BEARER_TOKEN).
    """
    token = explicit_token or config.BGG_BEARER_TOKEN
    if not token:
        logger.error("BGG_BEARER_TOKEN не задан в конфигурации")
        raise ValueError(
            "Не задан Bearer‑токен BGG. "
            "Передайте его параметром token=... или установите переменную окружения BGG_BEARER_TOKEN."
        )
    logger.debug("BGG токен успешно получен")
    return token


def _build_headers(token: Optional[str] = None) -> Dict[str, str]:
    """
    Формирует заголовки авторизации для запросов к BGG.
    """
    resolved = _resolve_token(token)
    return {"Authorization": f"Bearer {resolved}"}


def search_boardgame(
    name: str,
    exact: bool = False,
    *,
    token: Optional[str] = None,
    retries: int = 3,
    timeout: int = 15,
) -> List[Dict[str, Any]]:
    """
    Ищет настольные игры по названию через BGG XML API v2.

    :param name: Название игры (или его часть).
    :param exact: Если True — ищет только точные совпадения.
    :param retries: Кол-во попыток при нестабильности API.
    :param timeout: Таймаут HTTP‑запроса в секундах.
    :return: Список словарей с полями: id, name, yearpublished.
    """
    headers = _build_headers(token)

    params = {
        "query": name,
        "type": "boardgame",
        "exact": 1 if exact else 0,
    }

    logger.info(f"Поиск игры на BGG: query='{name}', exact={exact}")
    logger.debug(f"BGG search URL: {BGG_SEARCH_URL}, params={params}")

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            logger.debug(f"Попытка {attempt}/{retries} запроса к BGG search API")
            resp = requests.get(
                BGG_SEARCH_URL,
                params=params,
                headers=headers,
                timeout=timeout,
            )
            logger.debug(f"BGG search ответ: status_code={resp.status_code}, content_length={len(resp.text)}")
            resp.raise_for_status()

            # BGG иногда отвечает пустым телом при 200 OK — проверим это.
            if not resp.text.strip():
                logger.warning(f"BGG вернул пустой ответ для запроса '{name}'")
                raise RuntimeError("Пустой ответ от BGG")

            results = _parse_search_response(resp.text)
            logger.info(f"BGG search успешен: найдено {len(results)} игр для запроса '{name}'")
            if results:
                logger.debug(f"Найденные игры: {[r.get('name') for r in results[:3]]}")
            return results
        except requests.exceptions.RequestException as exc:
            last_error = exc
            logger.warning(f"Ошибка HTTP запроса к BGG (попытка {attempt}/{retries}): {exc}")
            if attempt < retries:
                # Небольшая пауза перед повтором
                time.sleep(1.5)
            else:
                logger.error(f"Не удалось выполнить запрос к BGG search API после {retries} попыток: {exc}")
                raise RuntimeError(f"Ошибка обращения к BGG API после {retries} попыток: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.error(f"Неожиданная ошибка при поиске игры '{name}' (попытка {attempt}/{retries}): {exc}", exc_info=True)
            if attempt < retries:
                time.sleep(1.5)
            else:
                raise RuntimeError(f"Ошибка обращения к BGG API после {retries} попыток: {exc}") from exc

    # Теоретически сюда не дойдём из-за raise выше, но оставим для типа.
    raise RuntimeError(f"Не удалось выполнить запрос к BGG API: {last_error}")


def get_boardgame_details(
    game_id: int,
    *,
    token: Optional[str] = None,
    retries: int = 3,
    timeout: int = 15,
) -> Dict[str, Any]:
    """
    Получает подробную информацию и рейтинг игры по её ID.

    На выходе минимум:
    - id: int
    - name: str | None
    - yearpublished: int | None
    - rank: int | None                # место в общем рейтинге boardgame
    - bayesaverage: float | None      # байесовский средний рейтинг
    - usersrated: int | None          # количество проголосовавших
    - image: str | None               # URL полноразмерного изображения
    - thumbnail: str | None           # URL уменьшенного изображения
    """
    headers = _build_headers(token)
    params = {
        "id": str(game_id),
        "stats": 1,
    }

    logger.info(f"Запрос деталей игры с BGG: game_id={game_id}")
    logger.debug(f"BGG thing URL: {BGG_THING_URL}, params={params}")

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            logger.debug(f"Попытка {attempt}/{retries} запроса к BGG thing API для game_id={game_id}")
            resp = requests.get(
                BGG_THING_URL,
                params=params,
                headers=headers,
                timeout=timeout,
            )
            logger.debug(f"BGG thing ответ: status_code={resp.status_code}, content_length={len(resp.text)}")
            resp.raise_for_status()

            if not resp.text.strip():
                logger.warning(f"BGG вернул пустой ответ для game_id={game_id}")
                raise RuntimeError("Пустой ответ от BGG при запросе статистики игры")

            result = _parse_thing_response(resp.text)
            logger.info(f"BGG thing успешен для game_id={game_id}: name='{result.get('name')}', rank={result.get('rank')}")
            return result
        except requests.exceptions.RequestException as exc:
            last_error = exc
            logger.warning(f"Ошибка HTTP запроса к BGG thing (попытка {attempt}/{retries}) для game_id={game_id}: {exc}")
            if attempt < retries:
                time.sleep(1.5)
            else:
                logger.error(f"Не удалось получить детали игры game_id={game_id} после {retries} попыток: {exc}")
                raise RuntimeError(
                    f"Ошибка обращения к BGG API (thing) после {retries} попыток: {exc}"
                ) from exc
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.error(f"Неожиданная ошибка при получении деталей игры game_id={game_id} (попытка {attempt}/{retries}): {exc}", exc_info=True)
            if attempt < retries:
                time.sleep(1.5)
            else:
                raise RuntimeError(
                    f"Ошибка обращения к BGG API (thing) после {retries} попыток: {exc}"
                ) from exc

    raise RuntimeError(f"Не удалось получить статистику игры: {last_error}")


def _parse_search_response(xml_text: str) -> List[Dict[str, Any]]:
    """Парсит XML‑ответ поиска BGG в удобную структуру."""
    try:
        root = ET.fromstring(xml_text)
        items = root.findall("item")
        logger.debug(f"Парсинг BGG search ответа: найдено {len(items)} элементов item")
        
        results: List[Dict[str, Any]] = []

        for item in items:
            game_id = item.attrib.get("id")

            # Внутри item есть дочерний элемент <name value="...">
            name_el = item.find("name")
            name = name_el.attrib.get("value") if name_el is not None else None

            year_el = item.find("yearpublished")
            year = year_el.attrib.get("value") if year_el is not None else None

            if not game_id:
                logger.warning(f"Найден item без id в ответе BGG search")
                continue

            results.append(
                {
                    "id": int(game_id) if game_id is not None else None,
                    "name": name,
                    "yearpublished": int(year) if year is not None and year.isdigit() else None,
                }
            )
        
        logger.debug(f"Успешно распарсено {len(results)} игр из BGG search ответа")
        return results
    except ET.ParseError as e:
        logger.error(f"Ошибка парсинга XML ответа BGG search: {e}")
        logger.debug(f"XML содержимое (первые 500 символов): {xml_text[:500]}")
        raise RuntimeError(f"Не удалось распарсить ответ BGG: {e}") from e


def _parse_thing_response(xml_text: str) -> Dict[str, Any]:
    """Парсит XML‑ответ /thing?stats=1 в словарь с рейтингом и статистикой."""
    try:
        root = ET.fromstring(xml_text)
        item = root.find("item")
        if item is None:
            logger.error("Ответ BGG thing не содержит элемента item")
            logger.debug(f"XML содержимое (первые 500 символов): {xml_text[:500]}")
            raise RuntimeError("Ответ BGG не содержит элемента item")
    except ET.ParseError as e:
        logger.error(f"Ошибка парсинга XML ответа BGG thing: {e}")
        logger.debug(f"XML содержимое (первые 500 символов): {xml_text[:500]}")
        raise RuntimeError(f"Не удалось распарсить ответ BGG: {e}") from e

    game_id = item.attrib.get("id")
    name_el = item.find("name")
    name = name_el.attrib.get("value") if name_el is not None else None

    year_el = item.find("yearpublished")
    year = year_el.attrib.get("value") if year_el is not None else None

    stats_el = item.find("statistics/ratings")
    usersrated_el = stats_el.find("usersrated") if stats_el is not None else None
    bayesavg_el = stats_el.find("bayesaverage") if stats_el is not None else None
    ranks_parent = stats_el.find("ranks") if stats_el is not None else None

    # Описание
    description_el = item.find("description")
    # В XML BGG описание может содержать HTML‑сущности и переводы строк.
    description_text = description_el.text if description_el is not None else None

    # Изображения
    image_el = item.find("image")
    thumb_el = item.find("thumbnail")
    image_url = image_el.text if image_el is not None else None
    thumb_url = thumb_el.text if thumb_el is not None else None

    # Ищем общий ранг по всей базе настолок (name="boardgame")
    world_rank: int | None = None
    if ranks_parent is not None:
        for rank_el in ranks_parent.findall("rank"):
            if rank_el.attrib.get("name") == "boardgame":
                value = rank_el.attrib.get("value")
                if value and value.isdigit():
                    world_rank = int(value)
                break

    def _to_int(text: str | None) -> int | None:
        return int(text) if text and text.isdigit() else None

    def _to_float(text: str | None) -> float | None:
        try:
            return float(text) if text is not None and text != "N/A" else None
        except ValueError:
            return None

    return {
        "id": _to_int(game_id),
        "name": name,
        "yearpublished": _to_int(year),
        "rank": world_rank,
        "bayesaverage": _to_float(bayesavg_el.attrib.get("value") if bayesavg_el is not None else None),
        "usersrated": _to_int(usersrated_el.attrib.get("value") if usersrated_el is not None else None),
        "image": image_url,
        "thumbnail": thumb_url,
        "description": description_text,
    }



