"""Integration tests for the git repos agent."""
import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import shutil
import git

from app.agents.git_repos_agent import (
    process_repositories,
    download_repository,
    EXCLUDED_FILES,
    EXCLUDED_DIRS
)

# Test Data Constants
TEST_REPO_URL = "https://github.com/test/repo.git"
TEST_REPO_NAME = "repo"

TEST_FILES = {
    "test.py": "print('test')",
    "test.md": "# Test",
    "README.md": "# Project"
}

EXCLUDED_TEST_FILES = {
    "test.png": b"binary",
    "package-lock.json": "{}",
    "node_modules/test.js": "console.log('test')"
}


def create_test_files(directory: Path) -> None:
    """Create a standard set of test files in the given directory.

    Args:
        directory: Path to create the test files in
    """
    # Create included files
    for filename, content in TEST_FILES.items():
        (directory / filename).write_text(content)


def create_excluded_files(directory: Path) -> None:
    """Create excluded test files and directories.

    Args:
        directory: Path to create the excluded files in
    """
    for filepath, content in EXCLUDED_TEST_FILES.items():
        full_path = directory / filepath
        full_path.parent.mkdir(exist_ok=True, parents=True)
        if isinstance(content, bytes):
            full_path.write_bytes(content)
        else:
            full_path.write_text(content)


@pytest.fixture
def mock_git_repo():
    """Create a mock git repository for testing.

    Instead of creating a real git repository, this creates a directory structure
    and mocks the git operations to simulate a git repository.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_dir = Path(temp_dir)

        # Create all test files
        create_test_files(repo_dir)
        create_excluded_files(repo_dir)

        # Create mock git repo instead of real one
        mock_repo = MagicMock(spec=git.Repo)
        mock_repo.working_dir = str(repo_dir)
        mock_repo.index = MagicMock()

        # Mock the git operations
        with patch('git.Repo') as mock_git:
            mock_git.init.return_value = mock_repo
            mock_git.clone_from.return_value = mock_repo
            yield repo_dir


@pytest.fixture
def patch_data_paths():
    """Patch the data paths to use relative paths for testing."""
    with patch('app.agents.git_repos_agent.DATA_DIR', Path("data")), \
         patch('app.agents.git_repos_agent.CODEBASE_DIR', Path("data/codebase")):
        # Create the directory if it doesn't exist
        codebase_dir = Path("data/codebase")
        codebase_dir.mkdir(parents=True, exist_ok=True)
        yield
        # Clean up after test
        if codebase_dir.exists():
            shutil.rmtree(codebase_dir.parent)


@pytest.mark.asyncio
async def test_process_repositories_success(patch_data_paths):
    """Test processing a repository successfully."""
    # Given: A repository URL
    with patch('git.Repo.clone_from') as mock_clone:
        # Create a temporary directory structure that mimics a cloned repo
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)

            # Create test files to simulate cloned content
            create_test_files(repo_dir)
            create_excluded_files(repo_dir)

            # Setup mock to "clone" to our test directory
            def mock_clone_effect(url, path):
                os.makedirs(path, exist_ok=True)
                for item in repo_dir.iterdir():
                    if item.is_file():
                        shutil.copy2(item, Path(path) / item.name)
                    else:
                        shutil.copytree(item, Path(path) / item.name)
            mock_clone.side_effect = mock_clone_effect

            # When: Processing the repository
            result = await process_repositories(TEST_REPO_URL)

            # Then: Verify the output file exists and contains expected content
            assert result.exists()
            assert result.is_file()
            content = result.read_text()

            # Check included content is present
            for filename, file_content in TEST_FILES.items():
                assert filename in content, f"Expected {filename} to be in content"
                assert file_content in content, f"Expected content of {filename} to be present"

            # Check excluded content is absent
            for filepath, _ in EXCLUDED_TEST_FILES.items():
                filename = Path(filepath).name
                assert filename not in content, f"Expected {filename} to be excluded"


@pytest.mark.asyncio
async def test_process_repositories_error_handling(patch_data_paths):
    """Test error handling when processing repositories."""
    # Given: A repository URL that will cause an error
    with patch('git.Repo.clone_from', side_effect=git.GitCommandError("clone", "Connection failed")):
        # When/Then: Processing should raise the error
        with pytest.raises(Exception) as exc_info:
            await process_repositories(TEST_REPO_URL)
        assert "Connection failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_download_repository_success():
    """Test downloading a repository successfully."""
    # Given: A repository URL and mocked git clone
    with patch('git.Repo.clone_from') as mock_clone:
        # Create a test directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)

            # Setup mock to create test files
            def mock_clone_effect(url, path):
                os.makedirs(path, exist_ok=True)
                (Path(path) / "test.py").write_text("print('test')")
                (Path(path) / "README.md").write_text("# Project")
            mock_clone.side_effect = mock_clone_effect

            # When: Downloading the repository
            repo_path, temp_dir_obj = await download_repository(TEST_REPO_URL)

            try:
                # Then: Verify the repository was downloaded correctly
                assert repo_path.exists()
                assert (repo_path / "test.py").exists()
                assert (repo_path / "README.md").exists()

                # Verify temp directory management
                assert isinstance(temp_dir_obj, tempfile.TemporaryDirectory)
                assert repo_path == Path(temp_dir_obj.name)
            finally:
                # Cleanup
                temp_dir_obj.cleanup()


@pytest.mark.asyncio
async def test_download_repository_error():
    """Test error handling when downloading repository fails."""
    # Given: A repository URL that will cause a git error
    with patch('git.Repo.clone_from', side_effect=git.GitCommandError("clone", "Repository not found")):
        # When/Then: Download should raise the error
        with pytest.raises(Exception) as exc_info:
            await download_repository(TEST_REPO_URL)
        assert "Repository not found" in str(exc_info.value)
