"""Git Repos Agent for handling repository operations."""
import os
import git
from pathlib import Path
from typing import List, Tuple
from app.common.logging import get_logger
from app.config.config import settings
import tempfile

logger = get_logger(__name__)

STANDARDS_REPO = "https://github.com/DEFRA/software-development-standards"
DATA_DIR = Path("/app/data")
CODEBASE_DIR = DATA_DIR / "codebase"

# Files to exclude when flattening
EXCLUDED_FILES = {
    # Binary files
    '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip',
    # Package lock files
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
    'poetry.lock', 'Pipfile.lock', 'composer.lock',
    'Gemfile.lock', 'cargo.lock', 'packages.lock.json'
}

# Directories to exclude
EXCLUDED_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}

def configure_git_proxy():
    """Configure git proxy settings from environment variables.
    
    Priority order:
    1. Use CDP_HTTPS_PROXY if available
    2. Fall back to CDP_HTTP_PROXY if HTTPS proxy not available
    3. Do nothing if neither proxy is configured
    """
    if settings.CDP_HTTPS_PROXY:
        logger.debug("Configuring git HTTPS proxy")
        git.Git().config("--global", "https.proxy", settings.CDP_HTTPS_PROXY)
        git.Git().config("--global", "http.proxy", settings.CDP_HTTPS_PROXY)
    elif settings.CDP_HTTP_PROXY:
        logger.debug("Configuring git HTTP proxy")
        git.Git().config("--global", "https.proxy", settings.CDP_HTTP_PROXY)
        git.Git().config("--global", "http.proxy", settings.CDP_HTTP_PROXY)
    else:
        logger.debug("No proxy configuration found")

async def flatten_repository(repo_path: Path, output_file: Path) -> None:
    """Flatten a repository's files into a single text file."""
    logger.debug(f"Flattening repository at {repo_path} to {output_file}")

    with open(output_file, 'w', encoding='utf-8') as f:
        for root, dirs, files in os.walk(repo_path):
            # Modify dirs in place to exclude unwanted directories
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

            for file in files:
                # Skip excluded files
                if any(file.endswith(ext) for ext in EXCLUDED_FILES) or any(file == excluded for excluded in EXCLUDED_FILES):
                    logger.debug(f"Skipping excluded file: {file}")
                    continue

                file_path = Path(root) / file
                try:
                    with open(file_path, 'r', encoding='utf-8') as source_file:
                        relative_path = file_path.relative_to(repo_path)
                        f.write(f"\n# File: {relative_path}\n")
                        f.write(source_file.read())
                        f.write("\n")
                except (UnicodeDecodeError, IOError) as e:
                    logger.warning(f"Skipping file {file_path}: {str(e)}")


async def clone_repo(repo_url: str, target_dir: Path) -> None:
    """Clone a git repository to the target directory."""
    logger.info(f"Cloning repository {repo_url} to {target_dir}")
    if target_dir.exists():
        logger.info(f"Removing existing directory: {target_dir}")
        import shutil
        shutil.rmtree(target_dir)

    # Configure proxy before git operations
    configure_git_proxy()
    
    git.Repo.clone_from(repo_url, str(target_dir))


async def download_repository(repository_url: str) -> Tuple[Path, tempfile.TemporaryDirectory]:
    """Download the repository to a temporary directory.

    Args:
        repository_url: URL of the Git repository to clone

    Returns:
        Tuple[Path, TemporaryDirectory]: Path to the cloned repository and the temp directory object
    """
    logger.info(f"Downloading repository {repository_url}")
    temp_dir = tempfile.TemporaryDirectory()
    temp_path = Path(temp_dir.name)
    
    try:
        await clone_repo(repository_url, temp_path)
        logger.info(f"Repository cloned successfully to {temp_path}")
        return temp_path, temp_dir
    except Exception as e:
        # Clean up the temporary directory if an error occurs during cloning
        temp_dir.cleanup()
        logger.error(f"Failed to clone repository {repository_url}: {str(e)}")
        raise


async def process_repositories(repository_url: str) -> Path:
    """Process the code repository."""
    temp_dir = None
    try:
        # Create necessary directories
        CODEBASE_DIR.mkdir(parents=True, exist_ok=True)

        # Extract repo name from URL
        repo_name = os.path.basename(repository_url).replace('.git', '')
        codebase_file = CODEBASE_DIR / f"{repo_name}.txt"

        # Using context manager for automatic cleanup
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            code_repo_dir = temp_path / "code"

            # Clone and process code repository
            await clone_repo(repository_url, code_repo_dir)
            await flatten_repository(code_repo_dir, codebase_file)

            return codebase_file

    except Exception as e:
        logger.error(f"Failed to process repository {repository_url}: {str(e)}", 
                    exc_info=True)
        raise
