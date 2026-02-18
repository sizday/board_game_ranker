"""
Unit tests for bot handlers
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from aiogram.types import Message

from bot.handlers.bgg_game import cmd_game


class TestGameCommand:
    """Test cases for game command handler"""

    @pytest.mark.asyncio
    async def test_cmd_game_no_query(self):
        """Test game command without query parameter"""
        mock_message = Mock(spec=Message)
        mock_message.text = "/game"
        mock_message.from_user.id = 12345
        mock_message.from_user.full_name = "Test User"
        mock_message.answer = AsyncMock()

        await cmd_game(mock_message, "http://test.com")

        mock_message.answer.assert_called_once_with(
            "Пожалуйста, укажи название игры. Пример:\n/game Terraforming Mars"
        )

    @pytest.mark.asyncio
    async def test_cmd_game_empty_query(self):
        """Test game command with empty query"""
        mock_message = Mock(spec=Message)
        mock_message.text = "/game   "
        mock_message.from_user.id = 12345
        mock_message.from_user.full_name = "Test User"
        mock_message.answer = AsyncMock()

        await cmd_game(mock_message, "http://test.com")

        mock_message.answer.assert_called_once_with("Название игры не должно быть пустым.")

    @pytest.mark.asyncio
    async def test_cmd_game_found_in_db_russian(self):
        """Test game command when game is found in database, Russian language"""
        mock_message = Mock(spec=Message)
        mock_message.text = "/game Test Game"
        mock_message.from_user.id = 12345
        mock_message.from_user.full_name = "Test User"
        mock_message.answer_photo = AsyncMock()

        # Mock httpx response for database search
        mock_response_data = {
            "games": [{
                "id": 1,
                "name": "Test Game",
                "yearpublished": 2020,
                "usersrated": 1000,
                "bgg_rank": 50,
                "average": 8.0,
                "description": "English description",
                "description_ru": "Русское описание",
                "image": "http://example.com/image.jpg"
            }]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_client.get.return_value.__aenter__.return_value = mock_response

            await cmd_game(mock_message, "http://test.com", "ru")

            # Should call database search first
            assert mock_client.get.call_count >= 1

            # Should send photo with Russian description
            mock_message.answer_photo.assert_called_once()
            call_args = mock_message.answer_photo.call_args
            assert "Русское описание" in call_args[1]["caption"]

    @pytest.mark.asyncio
    async def test_cmd_game_found_in_db_english(self):
        """Test game command when game is found in database, English language"""
        mock_message = Mock(spec=Message)
        mock_message.text = "/game Test Game"
        mock_message.from_user.id = 12345
        mock_message.from_user.full_name = "Test User"
        mock_message.answer_photo = AsyncMock()

        # Mock httpx response for database search
        mock_response_data = {
            "games": [{
                "id": 1,
                "name": "Test Game",
                "yearpublished": 2020,
                "usersrated": 1000,
                "bgg_rank": 50,
                "average": 8.0,
                "description": "English description",
                "description_ru": None,  # No Russian translation
                "image": "http://example.com/image.jpg"
            }]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_client.get.return_value.__aenter__.return_value = mock_response

            await cmd_game(mock_message, "http://test.com", "en")

            # Should send photo with English description
            mock_message.answer_photo.assert_called_once()
            call_args = mock_message.answer_photo.call_args
            assert "English description" in call_args[1]["caption"]

    @pytest.mark.asyncio
    async def test_cmd_game_found_on_bgg_and_saved(self):
        """Test game command when game is found on BGG and saved to database"""
        mock_message = Mock(spec=Message)
        mock_message.text = "/game New Game"
        mock_message.from_user.id = 12345
        mock_message.from_user.full_name = "Test User"
        mock_message.answer_photo = AsyncMock()

        # Mock empty database response
        db_response_data = {"games": []}

        # Mock BGG response
        bgg_response_data = {
            "games": [{
                "id": 99999,
                "name": "New Game",
                "yearpublished": 2023,
                "rank": 200,
                "average": 7.5,
                "description": "New game description",
                "image": "http://example.com/new.jpg"
            }]
        }

        # Mock save response
        save_response_data = {
            "id": 1,
            "name": "New Game",
            "bgg_id": 99999
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Configure different responses for different calls
            mock_responses = []
            for data in [db_response_data, bgg_response_data, save_response_data]:
                mock_resp = Mock()
                mock_resp.json.return_value = data
                mock_resp.raise_for_status.return_value = None
                mock_responses.append(mock_resp)

            mock_client.get.side_effect = mock_responses[:2]  # DB search and BGG search
            mock_client.post.return_value.__aenter__.return_value = mock_responses[2]  # Save operation

            await cmd_game(mock_message, "http://test.com", "ru")

            # Should search database first
            # Then search BGG
            # Then save to database
            # Finally display result
            assert mock_client.get.call_count == 2  # DB + BGG searches
            assert mock_client.post.call_count == 1  # Save operation
            mock_message.answer_photo.assert_called_once()