"""Integration tests for standards agent.

This module contains integration tests for the standards processing agent functionality.
Tests cover the complete flow of standards processing including:
- Standard set processing
- Individual standard analysis
- File processing
- Classification integration
- Error handling scenarios

Test data is currently defined in this file but should be moved to test_data.py in a future update.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from bson import ObjectId
from typing import Tuple, List

from app.agents.standards_agent import (
    process_standard_set,
    StandardsProcessingError,
    StandardAnalysisError,
    StandardsConfig,
    analyze_standard,
    process_standards,
    get_files_to_process,
    process_standard_file
)
from app.models.classification import Classification
from app.utils.anthropic_client import AnthropicClient
from tests.utils.test_data import (
    create_standards_agent_test_data,
    create_classification_docs,
    create_standard_content
)

# Test Data Setup
MOCK_STANDARD_SET_ID, MOCK_REPO_URL = create_standards_agent_test_data()
MOCK_CLASSIFICATION_DOCS = create_classification_docs()
MOCK_CLASSIFICATIONS = [
    Classification.model_validate({**doc, "_id": str(doc["_id"])})
    for doc in MOCK_CLASSIFICATION_DOCS
]

# Test Cases - Standard Set Processing


async def test_process_standard_set_success(
    standards_mock_collections: Tuple[AsyncMock, AsyncMock, AsyncMock],
    standards_test_files: Path,
    standards_env_setup: None
):
    """Test successful processing of a standard set.

    Verifies that standards are properly processed and stored when given valid input.
    """
    standards_collection, classifications_collection, _ = standards_mock_collections

    # Given: A valid repository with standards
    with patch("app.agents.standards_agent.get_database",
               return_value=standards_collection.database), \
            patch("app.agents.standards_agent.download_repository",
                  return_value=(standards_test_files, MagicMock())), \
            patch("app.agents.standards_agent.get_classifications",
                  return_value=MOCK_CLASSIFICATIONS), \
            patch("app.agents.standards_agent.analyze_standard",
                  return_value=["Python", "FastAPI"]), \
            patch("app.agents.standards_agent.process_standard_file") as mock_process_file:

        # When: Processing the standard set
        await process_standard_set(MOCK_STANDARD_SET_ID, MOCK_REPO_URL)

        # Then: Standards should be deleted and files processed
        standards_collection.delete_many.assert_called_once_with(
            {"standard_set_id": ObjectId(MOCK_STANDARD_SET_ID)}
        )

        # Verify each standard file was processed
        assert mock_process_file.call_count == 2, "Expected both test.md and python.md to be processed"


async def test_process_standard_set_git_error(
    standards_mock_collections: Tuple[AsyncMock, AsyncMock, AsyncMock],
    standards_env_setup: None
):
    """Test handling of git repository download failures."""
    # Given: A failing git repository download
    with patch("app.agents.standards_agent.get_database",
               return_value=standards_mock_collections[0].database), \
        patch("app.agents.standards_agent.download_repository",
              side_effect=Exception("Git error")):
        # When/Then: Processing should raise appropriate error
        with pytest.raises(StandardsProcessingError) as exc_info:
            await process_standard_set(MOCK_STANDARD_SET_ID, MOCK_REPO_URL)
        assert "Git error" in str(
            exc_info.value), "Expected git error in exception message"

# Test Cases - Standard Analysis


async def test_analyze_standard_success(
    standards_env_setup: None,
    mock_anthropic_client: None
):
    """Test successful analysis of a standard with clear classification."""
    # Given: A standard with clear classification indicators
    content = create_standard_content(is_python=True)
    classifications = ["Python", "FastAPI"]

    # When: Analyzing the standard
    result = await analyze_standard(content, classifications)

    # Then: Should return correct classification
    assert "Python" in result, "Python classification not found in result"
    assert len(result) == 1, "Expected exactly one classification"


async def test_analyze_standard_empty_response(
    standards_env_setup: None,
    mock_anthropic_client: None
):
    """Test handling of universal standards (no specific classification)."""
    # Given: A universal standard with no specific classification
    content = create_standard_content(is_python=False)
    classifications = ["Python", "FastAPI"]

    # When: LLM returns empty classification
    with patch.object(
        AnthropicClient,
        "create_message",
        return_value=""
    ):
        # Then: Should handle empty response appropriately
        result = await analyze_standard(content, classifications)
        assert len(
            result) == 0, "Expected empty classification list for universal standard"


async def test_analyze_standard_error(
    standards_env_setup: None,
    mock_anthropic_client: None
):
    """Test handling of LLM analysis failures."""
    # Given: A standard to analyze
    content = "# Test Standard"
    classifications = ["Python"]

    # When: LLM fails
    with patch.object(
        AnthropicClient,
        "create_message",
        side_effect=Exception("LLM error")
    ):
        # Then: Should raise appropriate error
        with pytest.raises(StandardAnalysisError) as exc_info:
            await analyze_standard(content, classifications)
        assert "LLM error" in str(
            exc_info.value), "Expected LLM error in exception message"

# Test Cases - File Processing


async def test_process_standard_file_success(
    standards_mock_collections: Tuple[AsyncMock, AsyncMock, AsyncMock],
    standards_test_files: Path,
    standards_env_setup: None
):
    """Test successful processing of an individual standard file."""
    # Given: A valid standard file and mocked dependencies
    standards_collection, _, _ = standards_mock_collections
    test_file = standards_test_files / "standards" / "test.md"

    # When: Processing a standard file
    with patch("app.agents.standards_agent.analyze_standard",
               return_value=["Python"]):
        standards_collection.insert_one = AsyncMock()

        await process_standard_file(
            test_file,
            standards_test_files,
            ObjectId(MOCK_STANDARD_SET_ID),
            MOCK_CLASSIFICATIONS,
            standards_collection
        )

        # Then: Standard should be properly stored
        standards_collection.insert_one.assert_called_once()
        doc = standards_collection.insert_one.call_args[0][0]
        assert "text" in doc, "Standard text not found in stored document"
        assert doc["standard_set_id"] == ObjectId(
            MOCK_STANDARD_SET_ID), "Incorrect standard set ID"


async def test_process_standard_file_error(
    standards_mock_collections: Tuple[AsyncMock, AsyncMock, AsyncMock],
    standards_test_files: Path,
    standards_env_setup: None
):
    """Test handling of standard file processing errors."""
    # Given: A non-existent standard file
    standards_collection, _, _ = standards_mock_collections
    test_file = standards_test_files / "standards" / "nonexistent.md"

    # When/Then: Processing should fail appropriately
    with pytest.raises(StandardsProcessingError) as exc_info:
        await process_standard_file(
            test_file,
            standards_test_files,
            ObjectId(MOCK_STANDARD_SET_ID),
            MOCK_CLASSIFICATIONS,
            standards_collection
        )
    assert "Error processing standard" in str(
        exc_info.value), "Expected file processing error message"

# Test Cases - Configuration and File Selection


async def test_get_files_to_process_testing_mode(standards_test_files: Path):
    """Test file filtering in testing mode with specific test files."""
    # Given: Testing mode configuration
    config = StandardsConfig()
    config.llm_testing = True
    config.testing_files = ["test.md"]

    # When: Getting files to process
    files = await get_files_to_process(standards_test_files, config)

    # Then: Should only include specified test files
    assert len(files) == 1, "Expected exactly one test file"
    assert any("test.md" in str(f)
               for root, f in files), "test.md not found in results"


async def test_get_files_to_process_normal_mode(standards_test_files: Path):
    """Test file filtering in normal processing mode."""
    # Given: Normal mode configuration
    config = StandardsConfig()
    config.llm_testing = False

    # When: Getting files to process
    files = await get_files_to_process(standards_test_files, config)

    # Then: Should include all markdown files
    # Both test.md and python.md
    assert len(files) == 2, "Expected both test.md and python.md"
