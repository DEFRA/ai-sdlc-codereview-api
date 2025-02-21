"""Integration tests for the Code Reviews Agent."""
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

import pytest
from bson import ObjectId

from app.agents.code_reviews_agent import (
    CodeReviewConfig,
    check_compliance,
    CodeReviewError
)
from app.utils.anthropic_client import AnthropicClient
from app.database.database_utils import get_database

# Test Data
MOCK_STANDARD = {
    "_id": ObjectId(),
    "text": "Code should follow PEP 8 style guidelines",
    "repository_path": "test_repo/file.py"
}

MOCK_CODEBASE = """
def bad_function():
    x=1
    y=2
    return x+y
"""

EXPECTED_REPORT_CONTENT = """# Test Standard Set Code Review
Date: """


@pytest.fixture
async def mock_database():
    """Mock database for testing."""
    mock_db = AsyncMock()
    mock_db.classifications = AsyncMock()

    # Create a mock cursor with to_list method
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[{"name": "PEP 8"}])

    # Make find return the mock cursor
    mock_db.classifications.find = MagicMock(return_value=mock_cursor)

    # Create a mock get_database function
    async def mock_get_database():
        return mock_db

    with patch('app.agents.code_reviews_agent.get_database', new=mock_get_database):
        yield mock_db


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic client responses."""
    with patch.object(AnthropicClient, 'create_message', new_callable=AsyncMock) as mock:
        mock.return_value = """## Standard: PEP 8 Style Guidelines

Compliant: <span style="color: #d4351c">**No**</span>

Relevant Files/Sections:
- test_repo/file.py

The code does not follow PEP 8 guidelines. Missing spaces around operators and no docstring.

## Specific Recommendations

- Add spaces around operators
- Add function docstring
"""
        yield mock


@pytest.fixture
def temp_codebase(tmp_path):
    """Create temporary codebase file."""
    codebase_file = tmp_path / "test_codebase.py"
    codebase_file.write_text(MOCK_CODEBASE)
    return codebase_file


@pytest.fixture(autouse=True)
async def setup_and_teardown():
    """Setup and teardown for each test."""
    # Setup - disable LLM testing by default
    os.environ["LLM_TESTING"] = "false"
    yield
    # Teardown
    if "LLM_TESTING" in os.environ:
        del os.environ["LLM_TESTING"]
    if "LLM_TESTING_STANDARDS_FILES" in os.environ:
        del os.environ["LLM_TESTING_STANDARDS_FILES"]

# Test Cases - Complete Code Review Flow


async def test_successful_code_review(
    mock_database,
    mock_anthropic,
    temp_codebase
):
    """Test successful end-to-end code review process."""
    # Given: A codebase and standards
    standards = [MOCK_STANDARD]
    review_id = "test_review"
    standard_set_name = "Test Standard Set"
    classification_ids = [str(ObjectId())]

    # When: Running a code review
    report_file = await check_compliance(
        codebase_file=temp_codebase,
        standards=standards,
        review_id=review_id,
        standard_set_name=standard_set_name,
        matching_classification_ids=classification_ids
    )

    # Then: Verify report was generated correctly
    assert report_file.exists()
    report_content = report_file.read_text()

    # Verify report structure
    assert standard_set_name in report_content
    assert "PEP 8" in report_content  # Classification name
    assert "Compliant: <span style=\"color: #d4351c\">**No**</span>" in report_content
    assert "test_repo/file.py" in report_content
    assert "Add spaces around operators" in report_content

    # Verify interactions
    mock_anthropic.assert_called_once()


async def test_code_review_with_llm_testing_enabled(
    mock_database,
    mock_anthropic,
    temp_codebase
):
    """Test code review with LLM testing mode enabled."""
    # Given: LLM testing enabled with specific test files
    os.environ["LLM_TESTING"] = "true"
    os.environ["LLM_TESTING_STANDARDS_FILES"] = "test_repo/file.py"

    standards = [
        MOCK_STANDARD,
        {
            "_id": ObjectId(),
            "text": "Should be filtered out",
            "repository_path": "other/path.py"
        }
    ]

    # When: Running a code review
    report_file = await check_compliance(
        codebase_file=temp_codebase,
        standards=standards,
        review_id="test_review",
        standard_set_name="Test Standard Set",
        matching_classification_ids=[str(ObjectId())]
    )

    # Then: Verify only matching standards were processed
    mock_anthropic.assert_called_once()  # Only one standard processed
    report_content = report_file.read_text()
    assert "Should be filtered out" not in report_content


async def test_code_review_with_invalid_codebase(
    mock_database,
    mock_anthropic
):
    """Test code review with non-existent codebase file."""
    # Given: A non-existent codebase file
    invalid_file = Path("nonexistent.py")

    # When/Then: Attempting code review should raise error
    with pytest.raises(CodeReviewError) as exc_info:
        await check_compliance(
            codebase_file=invalid_file,
            standards=[MOCK_STANDARD],
            review_id="test_review",
            standard_set_name="Test Standard Set",
            matching_classification_ids=[str(ObjectId())]
        )

    assert "Compliance check failed" in str(exc_info.value)
    mock_anthropic.assert_not_called()


async def test_code_review_with_anthropic_failure(
    mock_database,
    mock_anthropic,
    temp_codebase
):
    """Test code review when Anthropic API fails."""
    # Given: Anthropic API failure
    mock_anthropic.side_effect = Exception("API Error")

    # When/Then: Code review should handle error gracefully
    with pytest.raises(CodeReviewError) as exc_info:
        await check_compliance(
            codebase_file=temp_codebase,
            standards=[MOCK_STANDARD],
            review_id="test_review",
            standard_set_name="Test Standard Set",
            matching_classification_ids=[str(ObjectId())]
        )

    assert "Compliance check failed" in str(exc_info.value)
    assert "API Error" in str(exc_info.value)
    mock_anthropic.assert_called_once()


async def test_code_review_with_db_failure(
    mock_database,
    mock_anthropic,
    temp_codebase
):
    """Test code review when database operations fail."""
    # Given: Database failure at the fixture level
    mock_database.classifications.find.side_effect = Exception(
        "Database Error")

    # When/Then: Code review should handle error gracefully
    with pytest.raises(CodeReviewError) as exc_info:
        await check_compliance(
            codebase_file=temp_codebase,
            standards=[MOCK_STANDARD],
            review_id="test_review",
            standard_set_name="Test Standard Set",
            matching_classification_ids=[str(ObjectId())]
        )

    assert "Compliance check failed" in str(exc_info.value)
    assert "Database Error" in str(exc_info.value)
    mock_anthropic.assert_not_called()  # Should fail before reaching Anthropic API

# Test Cases - Process Code Review Flow


@pytest.fixture
async def mock_process_repositories():
    """Mock process_repositories function."""
    with patch('app.agents.code_reviews_agent.process_repositories') as mock:
        mock.return_value = Path("/tmp/test_codebase.py")
        yield mock


@pytest.fixture
async def mock_analyze_classifications():
    """Mock analyze_codebase_classifications function."""
    with patch('app.agents.code_reviews_agent.analyze_codebase_classifications') as mock:
        mock.return_value = [ObjectId()]
        yield mock


@pytest.fixture
async def mock_code_review_repo():
    """Mock CodeReviewRepository."""
    with patch('app.agents.code_reviews_agent.CodeReviewRepository') as mock:
        repo_instance = AsyncMock()
        mock.return_value = repo_instance
        yield repo_instance


@pytest.fixture
async def mock_check_compliance():
    """Mock check_compliance function."""
    with patch('app.agents.code_reviews_agent.check_compliance') as mock:
        # Create a mock Path class
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = "Mock compliance report content"
        mock_path.__str__.return_value = "/tmp/mock_report.md"

        mock.return_value = mock_path
        yield mock


async def test_process_code_review_success(
    mock_database,
    mock_anthropic,
    mock_process_repositories,
    mock_analyze_classifications,
    mock_code_review_repo,
    mock_check_compliance,
    temp_codebase
):
    """Test successful end-to-end process_code_review flow."""
    from app.agents.code_reviews_agent import process_code_review, ReviewStatus
    from app.models.classification import Classification

    # Given: Test data setup with consistent IDs
    standard_set_id = ObjectId()  # Create ID once and reuse
    review_id = str(ObjectId())
    repository_url = "https://github.com/test/repo"
    standard_sets = [str(standard_set_id)]  # Use the same ID

    # Mock database responses
    mock_database.classifications.find.return_value.to_list.return_value = [
        {"_id": ObjectId(), "name": "Python", "rules": []}
    ]
    mock_database.standard_sets.find_one.return_value = {
        "_id": standard_set_id,  # Use the same ID
        "name": "Test Standards"
    }
    mock_database.standards.find.return_value.to_list.return_value = [
        {"_id": ObjectId(), "text": "Test standard"}
    ]

    # When: Running the code review process
    await process_code_review(review_id, repository_url, standard_sets)

    # Then: Verify the process flow
    mock_code_review_repo.update_status.assert_any_call(
        review_id, ReviewStatus.IN_PROGRESS
    )
    mock_process_repositories.assert_called_once_with(repository_url)
    mock_analyze_classifications.assert_called_once()
    mock_check_compliance.assert_called_once()

    # Verify final status update
    final_call_args = mock_code_review_repo.update_status.call_args_list[-1]
    assert final_call_args[0][0] == review_id  # review_id
    assert final_call_args[0][1] == ReviewStatus.COMPLETED  # status
    assert isinstance(final_call_args[0][2], list)  # compliance_reports
    assert len(final_call_args[0][2]) == 1  # one standard set processed

    # Verify report content
    report = final_call_args[0][2][0]
    assert report["standard_set_name"] == "Test Standards"
    assert report["report"] == "Mock compliance report content"
    assert "_id" in report


async def test_process_code_review_with_invalid_standard_set(
    mock_database,
    mock_anthropic,
    mock_process_repositories,
    mock_analyze_classifications,
    mock_code_review_repo
):
    """Test process_code_review with invalid standard set ID."""
    from app.agents.code_reviews_agent import process_code_review, ReviewStatus

    # Given: Invalid standard set ID
    review_id = str(ObjectId())
    repository_url = "https://github.com/test/repo"
    standard_sets = ["invalid_id"]  # Invalid ObjectId format

    # Mock database responses
    mock_database.classifications.find.return_value.to_list.return_value = [
        {"_id": ObjectId(), "name": "Python", "rules": []}
    ]

    # When: Running the code review process
    await process_code_review(review_id, repository_url, standard_sets)

    # Then: Verify process completed with empty reports
    final_call_args = mock_code_review_repo.update_status.call_args_list[-1]
    assert final_call_args[0][0] == review_id
    assert final_call_args[0][1] == ReviewStatus.COMPLETED
    assert len(final_call_args[0][2]) == 0  # no reports generated


async def test_process_code_review_with_repository_error(
    mock_database,
    mock_anthropic,
    mock_process_repositories,
    mock_code_review_repo
):
    """Test process_code_review when repository processing fails."""
    from app.agents.code_reviews_agent import process_code_review, ReviewStatus, ProcessingError

    # Given: Repository processing error
    review_id = str(ObjectId())
    repository_url = "https://github.com/test/repo"
    standard_sets = [str(ObjectId())]
    mock_process_repositories.side_effect = Exception(
        "Repository processing failed")

    # When/Then: Process should handle error and update status
    with pytest.raises(ProcessingError) as exc_info:
        await process_code_review(review_id, repository_url, standard_sets)

    assert "Repository processing failed" in str(exc_info.value)
    mock_code_review_repo.update_status.assert_any_call(
        review_id, ReviewStatus.FAILED
    )


async def test_process_code_review_with_no_matching_standards(
    mock_database,
    mock_anthropic,
    mock_process_repositories,
    mock_analyze_classifications,
    mock_code_review_repo
):
    """Test process_code_review when no standards match the classifications."""
    from app.agents.code_reviews_agent import process_code_review, ReviewStatus

    # Given: Valid standard set but no matching standards
    review_id = str(ObjectId())
    repository_url = "https://github.com/test/repo"
    standard_sets = [str(ObjectId())]

    # Mock database responses
    mock_database.classifications.find.return_value.to_list.return_value = [
        {"_id": ObjectId(), "name": "Python", "rules": []}
    ]
    mock_database.standard_sets.find_one.return_value = {
        "_id": ObjectId(),
        "name": "Test Standards"
    }
    # No matching standards
    mock_database.standards.find.return_value.to_list.return_value = []

    # When: Running the code review process
    await process_code_review(review_id, repository_url, standard_sets)

    # Then: Process should complete with empty reports
    final_call_args = mock_code_review_repo.update_status.call_args_list[-1]
    assert final_call_args[0][0] == review_id
    assert final_call_args[0][1] == ReviewStatus.COMPLETED
    assert len(final_call_args[0][2]) == 0  # no reports generated
