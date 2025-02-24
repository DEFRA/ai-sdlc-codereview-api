"""Unit tests for logging configuration."""
import logging
import os
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml

from app.common.logging import configure_logging, get_logger


@pytest.fixture
def mock_yaml_config():
    """Basic logging config fixture."""
    return {
        "version": 1,
        "root": {
            "level": "INFO",
            "handlers": ["default"]
        },
        "formatters": {
            "default": {"format": ""},
            "access": {"format": ""}
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default"
            }
        },
        "loggers": {}  # Add empty loggers section
    }


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Reset logging config after each test."""
    yield
    logging.getLogger().handlers = []


@pytest.fixture
def mock_settings():
    """Mock settings fixture."""
    with patch("app.common.logging.settings") as mock_settings:
        mock_settings.LOG_LEVEL = "INFO"
        yield mock_settings


async def test_configure_logging_local_environment(mock_yaml_config, mock_settings):
    # Given: Local environment setup
    with patch.dict(os.environ, {"LOG_TYPE": "local"}), \
         patch("builtins.open", mock_open(read_data=yaml.dump(mock_yaml_config))), \
         patch("pathlib.Path.mkdir"):

        # When: Configure logging
        configure_logging()

        # Then: Verify local config
        root_logger = logging.getLogger()
        handlers = root_logger.handlers
        
        assert len(handlers) == 2  # Default + File handler
        assert any(isinstance(h, logging.FileHandler) for h in handlers)
        assert any(isinstance(h, logging.StreamHandler) for h in handlers)

        # Verify pymongo logger config
        pymongo_logger = logging.getLogger("pymongo")
        assert pymongo_logger.level == logging.WARNING
        assert not pymongo_logger.propagate


async def test_configure_logging_non_local_environment(mock_yaml_config, mock_settings):
    # Given: Non-local environment
    with patch.dict(os.environ, {"LOG_TYPE": "prod"}), \
         patch("builtins.open", mock_open(read_data=yaml.dump(mock_yaml_config))):

        # When: Configure logging
        configure_logging()

        # Then: Verify ECS formatting
        root_logger = logging.getLogger()
        handlers = root_logger.handlers
        
        assert len(handlers) == 1  # Only default handler
        assert isinstance(handlers[0], logging.StreamHandler)


async def test_get_logger():
    # Given: Logger name
    logger_name = "test_logger"

    # When: Get logger
    logger = get_logger(logger_name)

    # Then: Verify logger
    assert isinstance(logger, logging.Logger)
    assert logger.name == logger_name 