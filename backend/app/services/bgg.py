import time
from typing import List, Dict, Any, Optional

import xml.etree.ElementTree as ET

from app.config import config

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
        raise ValueError(
            "Не задан Bearer‑токен BGG. "
            "Передайте его параметром token=... или установите переменную окружения BGG_BEARER_TOKEN."
        )
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

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                BGG_SEARCH_URL,
                params=params,
                headers=headers,
                timeout=timeout,
            )
            resp.raise_for_status()

            # BGG иногда отвечает пустым телом при 200 OK — проверим это.
            if not resp.text.strip():
                raise RuntimeError("Пустой ответ от BGG")

            return _parse_search_response(resp.text)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries:
                # Небольшая пауза перед повтором
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

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                BGG_THING_URL,
                params=params,
                headers=headers,
                timeout=timeout,
            )
            resp.raise_for_status()

            if not resp.text.strip():
                raise RuntimeError("Пустой ответ от BGG при запросе статистики игры")

            return _parse_thing_response(resp.text)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries:
                time.sleep(1.5)
            else:
                raise RuntimeError(
                    f"Ошибка обращения к BGG API (thing) после {retries} попыток: {exc}"
                ) from exc

    raise RuntimeError(f"Не удалось получить статистику игры: {last_error}")


def _parse_search_response(xml_text: str) -> List[Dict[str, Any]]:
    """Парсит XML‑ответ поиска BGG в удобную структуру."""
    root = ET.fromstring(xml_text)
    results: List[Dict[str, Any]] = []

    for item in root.findall("item"):
        game_id = item.attrib.get("id")

        # Внутри item есть дочерний элемент <name value="...">
        name_el = item.find("name")
        name = name_el.attrib.get("value") if name_el is not None else None

        year_el = item.find("yearpublished")
        year = year_el.attrib.get("value") if year_el is not None else None

        results.append(
            {
                "id": int(game_id) if game_id is not None else None,
                "name": name,
                "yearpublished": int(year) if year is not None and year.isdigit() else None,
            }
        )

    return results


def _parse_thing_response(xml_text: str) -> Dict[str, Any]:
    """Парсит XML‑ответ /thing?stats=1 в словарь с рейтингом и статистикой."""
    root = ET.fromstring(xml_text)
    item = root.find("item")
    if item is None:
        raise RuntimeError("Ответ BGG не содержит элемента item")

    game_id = item.attrib.get("id")
    name_el = item.find("name")
    name = name_el.attrib.get("value") if name_el is not None else None

    year_el = item.find("yearpublished")
    year = year_el.attrib.get("value") if year_el is not None else None

    stats_el = item.find("statistics/ratings")
    usersrated_el = stats_el.find("usersrated") if stats_el is not None else None
    bayesavg_el = stats_el.find("bayesaverage") if stats_el is not None else None
    ranks_parent = stats_el.find("ranks") if stats_el is not None else None

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
    }



