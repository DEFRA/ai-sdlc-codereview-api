"""Functional tests for the Standards Classification Agent.

Tests the complete workflow of analyzing codebases for technology classifications.

Test Categories:
- Happy Path: Basic codebase analysis
- Edge Cases: Empty codebase, binary files
- Error Cases: Invalid paths, API failures

Key Fixtures:
- mock_codebase_path: Temporary directory with test files
- mock_anthropic: Mocked Anthropic client responses
"""
import os
from pathlib import Path
import pytest
from bson import ObjectId
from unittest.mock import AsyncMock, patch, MagicMock
from app.agents.standards_classification_agent import (
    analyze_codebase_classifications,
    ClassificationError,
)
from app.models.classification import Classification
from tests.utils.test_data import create_mock_classifications

# Test Cases - Happy Path


@pytest.fixture
def mock_codebase_path(tmp_path):
    """Create a temporary mock codebase directory.

    Args:
        tmp_path: Pytest fixture providing temporary directory

    Returns:
        Path: Configured temporary directory with test files
    """
    # Create test files
    main_py = tmp_path / "main.py"
    main_py.write_text("from fastapi import FastAPI\napp = FastAPI()")

    api_dir = tmp_path / "api"
    api_dir.mkdir()
    endpoints_py = api_dir / "endpoints.py"
    endpoints_py.write_text("def endpoint(): return {'status': 'ok'}")

    return tmp_path


@pytest.fixture
async def mock_anthropic():
    """Mock Anthropic client responses.

    Returns:
        MagicMock: Mocked Anthropic client with predefined responses
    """
    with patch("app.agents.standards_classification_agent.AnthropicClient") as mock:
        mock.create_message = AsyncMock(return_value="Python, FastAPI")
        yield mock


async def test_analyze_codebase_success(mock_codebase_path, mock_anthropic):
    """Test successful codebase analysis with valid classifications.

    Given: A codebase path and list of classifications
    When: Analyzing the codebase
    Then: Should return matching classification IDs
    """
    # Given: A codebase path and list of classifications
    mock_classifications = [Classification(
        **c) for c in create_mock_classifications()]

    # When: Analyzing the codebase
    result = await analyze_codebase_classifications(mock_codebase_path, mock_classifications)

    # Then: Should return matching classification IDs
    assert isinstance(result, list)
    assert mock_classifications[0].id in result  # Python
    assert mock_classifications[1].id in result  # FastAPI
    assert mock_anthropic.create_message.called

# Test Cases - Edge Cases


async def test_empty_codebase_analysis(mock_codebase_path, mock_anthropic):
    """Test analysis of empty codebase directory.

    Given: An empty directory
    When: Analyzing the codebase
    Then: Should return empty list
    """
    # Given: An empty directory
    for item in mock_codebase_path.iterdir():
        if item.is_file():
            item.unlink()
        else:
            for subitem in item.iterdir():
                subitem.unlink()
            item.rmdir()

    mock_anthropic.create_message = AsyncMock(return_value="")
    mock_classifications = [Classification(
        **c) for c in create_mock_classifications()]

    # When: Analyzing the codebase
    result = await analyze_codebase_classifications(mock_codebase_path, mock_classifications)

    # Then: Should return empty list
    assert result == []


async def test_binary_file_codebase_analysis(mock_codebase_path, mock_anthropic):
    """Test analysis of codebase with binary files.

    Given: A codebase with binary files
    When: Analyzing the codebase
    Then: Should process successfully and ignore binary files
    """
    # Given: A codebase with binary files
    binary_file = mock_codebase_path / "image.jpg"
    binary_file.write_bytes(b"binary content")

    mock_classifications = [Classification(
        **c) for c in create_mock_classifications()]

    # When: Analyzing the codebase
    result = await analyze_codebase_classifications(mock_codebase_path, mock_classifications)

    # Then: Should process successfully and ignore binary files
    assert isinstance(result, list)
    assert mock_classifications[0].id in result  # Python
    assert mock_classifications[1].id in result  # FastAPI

# Test Cases - Error Handling


async def test_invalid_codebase_path():
    """Test error handling for invalid codebase path.

    Given: An invalid path
    When: Analyzing the codebase
    Then: Should raise ClassificationError
    """
    # Given: An invalid path
    invalid_path = Path("/nonexistent/path")
    mock_classifications = [Classification(
        **c) for c in create_mock_classifications()]

    # When/Then: Should raise ClassificationError
    with pytest.raises(ClassificationError):
        await analyze_codebase_classifications(invalid_path, mock_classifications)


async def test_anthropic_api_failure(mock_codebase_path, mock_anthropic):
    """Test error handling for Anthropic API failure.

    Given: Anthropic API failure
    When: Analyzing the codebase
    Then: Should raise ClassificationError
    """
    # Given: Anthropic API failure
    mock_anthropic.create_message = AsyncMock(
        side_effect=Exception("API Error"))
    mock_classifications = [Classification(
        **c) for c in create_mock_classifications()]

    # When/Then: Should raise ClassificationError
    with pytest.raises(ClassificationError):
        await analyze_codebase_classifications(mock_codebase_path, mock_classifications)
