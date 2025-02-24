"""Logging configuration for the application."""
import logging
import logging.config
import os
from datetime import datetime
from pathlib import Path
import yaml
from app.config.config import settings

def configure_logging() -> None:
    """Configure logging for the application.
    
    Uses standard formatting for local development and ECS formatting for other environments.
    Adds file logging in local environment.
    """
    # Load base config
    with open("logging.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    # Set log level from settings
    config["root"]["level"] = settings.LOG_LEVEL
    
    # Configure formatters based on environment
    is_local = os.environ.get("LOG_TYPE", "").lower() == "local"
    standard_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Reduce MongoDB noise
    config["loggers"]["pymongo"] = {
        "level": "WARNING",
        "handlers": ["default"],
        "propagate": False
    }
    
    if is_local:
        # Use standard format for local development
        config["formatters"]["default"]["format"] = standard_format
        config["formatters"]["access"]["format"] = standard_format
        
        # Add file handler for local development
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        config["handlers"]["file"] = {
            "class": "logging.FileHandler",
            "filename": str(log_dir / f"app_{datetime.now():%Y%m%d_%H%M%S}.log"),
            "formatter": "default",
            "level": "DEBUG"
        }
        config["root"]["handlers"].append("file")
    else:
        # Use ECS format for non-local environments
        config["formatters"]["default"]["class"] = "ecs_logging.StdlibFormatter"
        config["formatters"]["access"]["class"] = "ecs_logging.StdlibFormatter"
    
    # Apply configuration
    logging.config.dictConfig(config)

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name."""
    return logging.getLogger(name)
