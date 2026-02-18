"""
Unit tests for games API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from backend.app.main import app
from backend.app.infrastructure.models import GameModel


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def sample_game(test_db):
    """Create a sample game in database"""
    game = GameModel(
        name="Test Game",
        bgg_id=12345,
        description="Test description",
        description_ru="Тестовое описание"
    )
    test_db.add(game)
    test_db.commit()
    test_db.refresh(game)
    return game


class TestGamesAPI:
    """Test cases for games API endpoints"""

    def test_search_games_in_db_success(self, client, sample_game):
        """Test successful search in database"""
        response = client.get("/api/games/search?name=Test")

        assert response.status_code == 200
        data = response.json()
        assert "games" in data
        assert len(data["games"]) == 1
        assert data["games"][0]["name"] == "Test Game"

    def test_search_games_in_db_no_results(self, client):
        """Test search with no results"""
        response = client.get("/api/games/search?name=NonExistent")

        assert response.status_code == 200
        data = response.json()
        assert "games" in data
        assert len(data["games"]) == 0

    def test_search_games_in_db_exact_match(self, client, sample_game):
        """Test exact match search"""
        response = client.get("/api/games/search?name=Test Game&exact=true")

        assert response.status_code == 200
        data = response.json()
        assert len(data["games"]) == 1
        assert data["games"][0]["name"] == "Test Game"

    def test_search_games_in_db_limit(self, client):
        """Test search with limit"""
        # Create multiple games
        for i in range(5):
            game = GameModel(name=f"Game {i}", bgg_id=1000 + i)
            client.app.state.db.add(game)
        client.app.state.db.commit()

        response = client.get("/api/games/search?name=Game&limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["games"]) == 2

    @patch("backend.app.api.games.save_game_from_bgg_data")
    @patch("backend.app.api.games.BackgroundTasks")
    def test_save_game_from_bgg_success(self, mock_background_tasks, mock_save_function, client, sample_bgg_response):
        """Test successful saving game from BGG data"""
        # Mock the save function
        mock_game = GameModel(
            id=1,
            name="Test Game",
            bgg_id=12345,
            description="Test description"
        )
        mock_save_function.return_value = mock_game

        bgg_data = {
            "id": 12345,
            "name": "Test Game",
            "description": "Test description"
        }

        response = client.post("/api/games/save-from-bgg", json=bgg_data)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "Test Game"
        mock_save_function.assert_called_once()
        # Check that background translation was scheduled
        mock_background_tasks.return_value.add_task.assert_called_once()

    def test_save_game_from_bgg_invalid_data(self, client):
        """Test saving game with invalid BGG data"""
        invalid_data = {
            "name": "",  # Invalid empty name
        }

        response = client.post("/api/games/save-from-bgg", json=invalid_data)

        assert response.status_code == 400