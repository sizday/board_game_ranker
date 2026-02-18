import asyncio
import logging
from typing import Optional

from sqlalchemy.orm import Session

try:
    from googletrans import Translator
    GOOGLETRANS_AVAILABLE = True
except ImportError:
    GOOGLETRANS_AVAILABLE = False
    logging.warning("googletrans not available, translation service will be disabled")

from app.config import config
from app.infrastructure.models import GameModel

logger = logging.getLogger(__name__)


class TranslationService:
    """
    Сервис для перевода текстов с использованием Google Translate API.
    """

    def __init__(self):
        logger.info("Initializing TranslationService...")
        self.translator = None
        if GOOGLETRANS_AVAILABLE:
            self.translator = Translator()
            logger.info("TranslationService initialized successfully with Google Translate")
        else:
            logger.error("Translation service unavailable: googletrans not installed")

        self.translation_count = 0
        self.error_count = 0
        logger.debug("TranslationService stats initialized: translations=0, errors=0")

    async def translate_to_russian(self, text: str) -> Optional[str]:
        """
        Переводит текст на русский язык.

        :param text: Исходный текст на английском
        :return: Переведенный текст или None при ошибке
        """
        if not text or not text.strip():
            logger.debug("Translation skipped: empty or whitespace-only text")
            return None

        if not self.translator:
            logger.warning("Translation service not available - cannot translate text")
            self.error_count += 1
            return None

        text_length = len(text)
        logger.debug(f"Starting translation of text ({text_length} chars)")

        try:
            # Google Translate работает синхронно, но мы запускаем в executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.translator.translate(text, src='en', dest='ru')
            )

            translated_text = result.text
            translated_length = len(translated_text)

            self.translation_count += 1
            logger.info(f"✅ Translation successful: {text_length} → {translated_length} chars "
                       f"(total: {self.translation_count}, errors: {self.error_count})")

            # Логируем первые 100 символов для отладки
            preview = translated_text[:100] + "..." if len(translated_text) > 100 else translated_text
            logger.debug(f"Translation preview: {preview}")

            return translated_text

        except Exception as e:
            self.error_count += 1
            logger.error(f"❌ Translation failed: {e} "
                        f"(total: {self.translation_count}, errors: {self.error_count})",
                        exc_info=True)
            return None

    async def is_available(self) -> bool:
        """Проверяет доступность сервиса перевода."""
        return self.translator is not None

    async def translate_game_descriptions_background(self, db: Session) -> None:
        """
        Фоновая задача для перевода описаний игр, у которых нет русского перевода.

        :param db: Сессия базы данных
        """
        logger.info("🔄 Starting background translation task")

        if not self.translator:
            logger.warning("❌ Translation service not available, skipping background translation")
            return

        try:
            # Находим игры без русского описания, но с английским
            games_to_translate = (
                db.query(GameModel)
                .filter(GameModel.description.isnot(None))
                .filter(GameModel.description_ru.is_(None))
                .filter(GameModel.description != '')
                .all()
            )

            total_games = len(games_to_translate)

            if not games_to_translate:
                logger.info("ℹ️  No games found that need translation")
                return

            logger.info(f"📚 Found {total_games} games that need translation")
            logger.info("🚀 Starting background translation process...")

            successful_translations = 0
            failed_translations = 0

            # Переводим описания по одному (чтобы не перегружать API)
            for i, game in enumerate(games_to_translate, 1):
                try:
                    logger.info(f"📖 [{i}/{total_games}] Translating game: {game.name} (ID: {game.id})")

                    translated_text = await self.translate_to_russian(game.description)
                    if translated_text:
                        game.description_ru = translated_text
                        successful_translations += 1
                        logger.info(f"✅ [{i}/{total_games}] Successfully translated: {game.name}")
                    else:
                        failed_translations += 1
                        logger.warning(f"⚠️  [{i}/{total_games}] Failed to translate: {game.name}")

                    # Небольшая задержка между запросами, чтобы не превысить лимиты API
                    await asyncio.sleep(0.5)

                    # Логируем прогресс каждые 10 игр
                    if i % 10 == 0:
                        logger.info(f"📊 Progress: {i}/{total_games} games processed "
                                  f"({successful_translations} successful, {failed_translations} failed)")

                except Exception as e:
                    failed_translations += 1
                    logger.error(f"❌ [{i}/{total_games}] Error translating game {game.name} (ID: {game.id}): {e}")
                    continue

            # Сохраняем изменения
            db.commit()

            logger.info("💾 Database changes committed")
            logger.info("🎉 Background translation completed!"            logger.info(f"📈 Final stats: {total_games} total, "
                      f"{successful_translations} successful, {failed_translations} failed")

        except Exception as e:
            logger.error("💥 Critical error in background translation task", exc_info=True)
            try:
                db.rollback()
                logger.info("🔄 Database transaction rolled back")
            except Exception as rollback_error:
                logger.error(f"❌ Failed to rollback transaction: {rollback_error}")


# Глобальный экземпляр сервиса
translation_service = TranslationService()


async def translate_game_descriptions_background(db: Session) -> None:
    """
    Фоновая задача для перевода описаний игр.
    Вызывается из FastAPI BackgroundTasks.

    :param db: Сессия базы данных
    """
    await translation_service.translate_game_descriptions_background(db)