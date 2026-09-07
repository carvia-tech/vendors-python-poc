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

    # Disambiguation Settings
    disambiguation_max_candidates: int = 5

    # Company Registry Settings (ZaubaCorp - Indian MCA registry data).
    # Used to attach a company's CIN and age since incorporation. Only
    # Indian (MCA-registered) companies exist in this registry, so a
    # non-Indian company legitimately resolves to no record.
    registry_enabled: bool = True
    registry_base_url: str = "https://www.zaubacorp.com"
    registry_timeout: int = 20
    registry_max_candidates: int = 40

    # Scraping Settings
    scraping_timeout: int = 15
    scraping_max_retries: int = 2
    scraping_max_content_length: int = 50000  # Limit text to avoid huge prompts

    # When a static (httpx) scrape comes back too thin - e.g. a JS-only or
    # geo-redirect-gated page like prolifics.com - retry once with a
    # headless browser that actually executes the page's JavaScript.
    scraping_playwright_fallback: bool = True
    scraping_playwright_timeout_ms: int = 20000

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
