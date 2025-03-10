#!/usr/bin/env python3
"""
Script to set up pre-commit hooks for the project.
Run this script after cloning the repository or after updating the hooks.
"""

import subprocess
import sys


def main():
    """Install and configure pre-commit hooks."""
    print("Setting up pre-commit hooks...")

    # Check if pre-commit is installed
    try:
        subprocess.run(["pre-commit", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("pre-commit not found. Installing pre-commit...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pre-commit"], check=True
        )

    # Install the pre-commit hooks
    subprocess.run(["pre-commit", "install"], check=True)

    print("Pre-commit hooks installed successfully!")
    print("Run 'pre-commit run --all-files' to test the hooks on all files.")


if __name__ == "__main__":
    main()
