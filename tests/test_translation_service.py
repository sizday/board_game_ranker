"""
Unit tests for translation service
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock

from backend.app.services.translation import TranslationService, translate_game_descriptions_background


class TestTranslationService:
    """Test cases for TranslationService"""

    def test_init_without_googletrans(self):
        """Test initialization when googletrans is not available"""
        with patch.dict('sys.modules', {'googletrans': None}):
            service = TranslationService()
            assert service.translator is None

    def test_init_with_googletrans(self):
        """Test initialization when googletrans is available"""
        with patch('backend.app.services.translation.googletrans') as mock_googletrans:
            mock_googletrans.Translator.return_value = Mock()
            service = TranslationService()
            assert service.translator is not None
            mock_googletrans.Translator.assert_called_once()

    def test_translate_empty_text(self):
        """Test translation of empty text"""
        service = TranslationService()
        result = service.translate_to_russian("")
        assert result is None

    def test_translate_none_text(self):
        """Test translation of None text"""
        service = TranslationService()
        result = service.translate_to_russian(None)
        assert result is None

    def test_translate_without_translator(self):
        """Test translation when translator is not available"""
        service = TranslationService()
        service.translator = None
        result = service.translate_to_russian("Hello world")
        assert result is None

    @pytest.mark.asyncio
    async def test_translate_success(self):
        """Test successful translation"""
        service = TranslationService()
        mock_result = Mock()
        mock_result.text = "Привет мир"

        with patch.object(service, 'translator') as mock_translator:
            mock_translator.translate.return_value = mock_result

            result = await service.translate_to_russian("Hello world")

            assert result == "Привет мир"
            mock_translator.translate.assert_called_once_with("Hello world", src='en', dest='ru')

    @pytest.mark.asyncio
    async def test_translate_exception(self):
        """Test translation with exception"""
        service = TranslationService()

        with patch.object(service, 'translator') as mock_translator:
            mock_translator.translate.side_effect = Exception("Translation failed")

            result = await service.translate_to_russian("Hello world")

            assert result is None

    def test_is_available_with_translator(self):
        """Test is_available when translator exists"""
        service = TranslationService()
        service.translator = Mock()
        assert service.is_available() is True

    def test_is_available_without_translator(self):
        """Test is_available when translator doesn't exist"""
        service = TranslationService()
        service.translator = None
        assert service.is_available() is False


class TestBackgroundTranslation:
    """Test cases for background translation function"""

    @pytest.mark.asyncio
    async def test_translate_game_descriptions_background(self):
        """Test background translation function"""
        mock_db = Mock()

        with patch('backend.app.services.translation.translation_service') as mock_service:
            mock_service.translate_game_descriptions_background = AsyncMock()

            await translate_game_descriptions_background(mock_db)

            mock_service.translate_game_descriptions_background.assert_called_once_with(mock_db)