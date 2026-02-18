"""
Pytest fixtures and configuration for testing
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.infrastructure.db import Base
from backend.app.infrastructure.models import GameModel, RatingModel, RankingSessionModel


@pytest.fixture
def test_db():
    """Create in-memory SQLite database for testing"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_game_data():
    """Sample game data for testing"""
    return {
        "id": 1,
        "name": "Test Game",
        "bgg_id": 12345,
        "bgg_rank": 100,
        "yearpublished": 2020,
        "average": 7.5,
        "bayesaverage": 7.2,
        "usersrated": 1500,
        "description": "This is a test game description.",
        "description_ru": "Это тестовое описание игры.",
        "image": "https://example.com/image.jpg",
        "thumbnail": "https://example.com/thumb.jpg"
    }


@pytest.fixture
def sample_bgg_response():
    """Sample BGG API response"""
    return {
        "id": 12345,
        "name": "Test Game",
        "yearpublished": 2020,
        "rank": 100,
        "average": 7.5,
        "bayesaverage": 7.2,
        "usersrated": 1500,
        "description": "This is a test game description.",
        "description_ru": None,
        "image": "https://example.com/image.jpg",
        "thumbnail": "https://example.com/thumb.jpg",
        "categories": ["Strategy"],
        "mechanics": ["Worker Placement"]
    }