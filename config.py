"""
Configuration settings for the Company Intelligence Engine.

This module contains all configuration settings including API endpoints,
search settings, and LLM configuration.
"""

from pathlib import Path

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""

    # Application settings
    app_name: str = "Company Information Intelligence Engine"
    app_version: str = "1.0.0"

    # FastAPI Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = False
    api_reload: bool = True
    cors_origins: list[str] = ["*"]

    # LLM Settings
    llm_api_key: Optional[str] = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    llm_timeout: int = 60

    # Search Settings
    search_max_results: int = 10
    search_timeout: int = 10

    # Scraping Settings
    scraping_timeout: int = 15
    scraping_max_retries: int = 2
    scraping_max_content_length: int = 50000  # Limit text to avoid huge prompts

    # Exclude domains
    excluded_domains: list[str] = [
        "wikipedia.org",
        "linkedin.com",
        "crunchbase.com",
        "glassdoor.com",
        "facebook.com",
        "twitter.com",
        "x.com",
        "instagram.com",
        "youtube.com",
        "indeed.com",
        "zoominfo.com",
        "bloomberg.com",
        "forbes.com",
    ]

    class Config:
        # Keep credentials outside the service directory.  This lets the API
        # receive only business data, never an LLM credential from callers.
        env_file = Path(__file__).resolve().parent.parent / ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
