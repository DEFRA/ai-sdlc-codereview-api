"""Configuration management for the application."""
from pydantic_settings import BaseSettings
from typing import Literal, List, Optional
from pydantic import ConfigDict, Field, field_validator, ValidationError

class Settings(BaseSettings):
    """Application settings."""
    # Required API settings
    MONGO_URI: str = "mongodb://127.0.0.1:27017/"
    ANTHROPIC_API_KEY: Optional[str] = None  # Made optional
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    
    # Anthropic settings
    ANTHROPIC_BEDROCK: str = "false"  # Controls whether to use AWS Bedrock or direct API
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    ANTHROPIC_MAX_TOKENS: int = 8192
    ANTHROPIC_TEMPERATURE: float = 0.0
    
    # AWS Bedrock settings
    AWS_ACCESS_KEY: str = ""
    AWS_SECRET_KEY: str = ""
    AWS_REGION: str = ""
    AWS_BEDROCK_MODEL: str = ""
    
    # Feature flags
    LLM_TESTING: bool = False
    LLM_TESTING_STANDARDS_FILES: str = ""
    
    # MongoDB Docker settings (optional with defaults)
    MONGO_DATABASE: str = "ai-sdlc-codereview-api"
    
    # Git proxy settings
    CDP_HTTP_PROXY: Optional[str] = None
    CDP_HTTPS_PROXY: Optional[str] = None
    
    @property
    def has_proxy_config(self) -> bool:
        """Check if proxy settings are configured."""
        return bool(self.CDP_HTTP_PROXY or self.CDP_HTTPS_PROXY)
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

settings = Settings() 