"""Test fixtures for the FastAPI application."""
from app.main import app
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from typing import Tuple, AsyncGenerator
from pathlib import Path


@pytest.fixture(autouse=True)
async def mock_database_setup():
    """Mock all database-related components."""
    mock_db = AsyncMock()
    mock_db.client = MagicMock()

    # Add attributes for each collection used across repositories
    for col in ["classifications", "code_reviews", "standard_sets", "standards"]:
        collection_mock = AsyncMock()
        collection_mock.database = mock_db
        setattr(mock_db, col, collection_mock)

    with patch("app.database.database_utils.initialize_database", return_value=None), \
            patch("app.database.database_utils.get_database", return_value=mock_db), \
            patch("app.database.database_utils.client", new=MagicMock()), \
            patch("motor.motor_asyncio.AsyncIOMotorClient", return_value=MagicMock()):

        app.state.db = mock_db
        yield mock_db


@pytest.fixture(autouse=True)
async def reset_app_state():
    """Reset application state before each test."""
    app.dependency_overrides = {}
    yield
    app.dependency_overrides = {}


@pytest.fixture
def client(mock_database_setup):
    """Create a test client for the FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client(mock_database_setup):
    """Create an async test client for the FastAPI application.

    Uses ASGITransport to make requests directly to the FastAPI app
    without making real HTTP calls.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Mock environment variables."""
    monkeypatch.setenv("MONGODB_URL", "mongodb://test:27017")
    monkeypatch.setenv("DATABASE_NAME", "test_db")


# Standards Agent Testing Fixtures
@pytest.fixture
async def standards_mock_collections(
    mock_database_setup: AsyncIOMotorDatabase
) -> Tuple[AsyncIOMotorCollection, AsyncIOMotorCollection, AsyncIOMotorCollection]:
    """Setup mock collections for standards processing tests.

    Configures mock collections with proper relationships and default behaviors
    for standards processing tests.

    Args:
        mock_database_setup: Base database mock from shared fixtures

    Returns:
        Tuple containing:
        - standards_collection: For storing processed standards
        - classifications_collection: For classification lookups
        - standard_sets_collection: For standard set metadata
    """
    from tests.utils.test_data import create_classification_docs

    standards_collection = AsyncMock()
    classifications_collection = AsyncMock()
    standard_sets_collection = AsyncMock()

    # Setup mock find operations to return proper cursor with raw documents
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=create_classification_docs())
    classifications_collection.find = MagicMock(return_value=mock_cursor)

    # Setup database relationship
    mock_db = AsyncMock()
    mock_db.get_collection = MagicMock(side_effect=lambda name: {
        "standards": standards_collection,
        "classifications": classifications_collection,
        "standard_sets": standard_sets_collection
    }[name])
    standards_collection.database = mock_db
    classifications_collection.database = mock_db
    standard_sets_collection.database = mock_db

    # Setup standard collection operations
    standards_collection.delete_many = AsyncMock()
    standards_collection.insert_one = AsyncMock()

    # Setup mock find operations for standards
    standards_mock_cursor = MagicMock()
    standards_mock_cursor.to_list = AsyncMock(return_value=[])
    standards_collection.find = MagicMock(return_value=standards_mock_cursor)

    return standards_collection, classifications_collection, standard_sets_collection


@pytest.fixture
async def mock_anthropic_client() -> AsyncGenerator[None, None]:
    """Mock Anthropic client for all tests.

    Provides a default mock that returns "Python" as classification.
    Tests can override this behavior with their own patches.

    Yields:
        None: This fixture is used for its side effects
    """
    from app.utils.anthropic_client import AnthropicClient

    with patch.object(
        AnthropicClient,
        "create_message",
        return_value="Python"  # Default classification for standards
    ):
        yield


@pytest.fixture
async def standards_env_setup(
    monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[None, None]:
    """Setup environment for standards processing tests.

    Configures environment variables and external dependencies
    required for standards processing.

    Args:
        monkeypatch: pytest fixture for modifying environment

    Yields:
        None: This fixture is used for its side effects
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-api-key")
    yield


@pytest.fixture
def standards_test_files(tmp_path: Path) -> Path:
    """Create temporary test standard files.

    Creates a simulated standards repository with test markdown files
    in a temporary directory that is cleaned up after the test.

    Args:
        tmp_path: pytest fixture providing temporary directory

    Returns:
        Path: Path to temporary repository directory containing test standards
    """
    repo_path = tmp_path / "standards_repo"
    standards_dir = repo_path / "standards"
    standards_dir.mkdir(parents=True)

    (standards_dir / "test.md").write_text("# Test Standard\nThis is a test standard.")
    (standards_dir / "python.md").write_text("# Python Standard\nThis is a Python standard.")

    return repo_path
