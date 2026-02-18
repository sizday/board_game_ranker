"""
Unit tests for repository functions
"""
import pytest

from backend.app.infrastructure.repositories import save_game_from_bgg_data
from backend.app.infrastructure.models import GameModel


class TestGameRepository:
    """Test cases for game repository functions"""

    def test_save_game_from_bgg_data_new_game(self, test_db, sample_bgg_response):
        """Test saving a new game from BGG data"""
        # Act
        game = save_game_from_bgg_data(test_db, sample_bgg_response)

        # Assert
        assert game.id is not None
        assert game.name == "Test Game"
        assert game.bgg_id == 12345
        assert game.bgg_rank == 100
        assert game.yearpublished == 2020
        assert game.average == 7.5
        assert game.bayesaverage == 7.2
        assert game.usersrated == 1500
        assert game.description == "This is a test game description."
        assert game.image == "https://example.com/image.jpg"
        assert game.thumbnail == "https://example.com/thumb.jpg"
        assert game.categories == ["Strategy"]
        assert game.mechanics == ["Worker Placement"]

        # Verify game was saved to database
        saved_game = test_db.query(GameModel).filter(GameModel.bgg_id == 12345).first()
        assert saved_game is not None
        assert saved_game.name == "Test Game"

    def test_save_game_from_bgg_data_existing_game(self, test_db, sample_bgg_response):
        """Test updating an existing game from BGG data"""
        # Arrange - create existing game
        existing_game = GameModel(
            name="Test Game",
            bgg_id=12345,
            description="Old description"
        )
        test_db.add(existing_game)
        test_db.commit()

        # Update BGG data
        updated_data = sample_bgg_response.copy()
        updated_data["description"] = "Updated description"

        # Act
        game = save_game_from_bgg_data(test_db, updated_data)

        # Assert
        assert game.id == existing_game.id
        assert game.description == "Updated description"

    def test_save_game_from_bgg_data_by_name(self, test_db, sample_bgg_response):
        """Test saving game that exists by name but not bgg_id"""
        # Arrange - create existing game by name only
        existing_game = GameModel(
            name="Test Game",
            description="Old description"
        )
        test_db.add(existing_game)
        test_db.commit()

        # Act
        game = save_game_from_bgg_data(test_db, sample_bgg_response)

        # Assert - should update existing game
        assert game.id == existing_game.id
        assert game.bgg_id == 12345  # Should be set now

    def test_save_game_from_bgg_data_invalid_data(self, test_db):
        """Test saving game with invalid data"""
        invalid_data = {
            "name": "",  # Empty name
            "id": None   # No ID
        }

        with pytest.raises(ValueError):
            save_game_from_bgg_data(test_db, invalid_data)