"""
Configuration settings for the Company Intelligence Engine.

This module contains all configuration settings including API endpoints,
search settings, LLM configuration, and company disambiguation settings.
"""

from pydantic_settings import BaseSettings
from typing import Optional, Dict, List


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

    # --- Company Disambiguation Settings ---

    # Region-to-TLD mapping for geo-aware URL scoring.
    # When a user specifies a region, TLDs matching that region get a score boost.
    region_tld_map: Dict[str, List[str]] = {
        "india": [".in", ".co.in", ".india"],
        "usa": [".us", ".com"],
        "united states": [".us", ".com"],
        "uk": [".co.uk", ".uk", ".org.uk"],
        "united kingdom": [".co.uk", ".uk", ".org.uk"],
        "germany": [".de"],
        "france": [".fr"],
        "japan": [".co.jp", ".jp"],
        "china": [".cn", ".com.cn"],
        "australia": [".com.au", ".au"],
        "canada": [".ca", ".co.ca"],
        "brazil": [".com.br", ".br"],
        "netherlands": [".nl"],
        "italy": [".it"],
        "spain": [".es"],
        "singapore": [".sg", ".com.sg"],
        "uae": [".ae"],
    }

    # Minimum confidence score (0-100) to accept a search result without AI disambiguation.
    # If top result confidence < this threshold AND an API key is available,
    # the AI disambiguator will be invoked to pick the best URL.
    disambiguation_min_confidence: int = 70

    # Maximum number of candidate URLs to send to AI for disambiguation.
    disambiguation_max_candidates: int = 5

    # Scoring weights for URL result ranking
    disambiguation_score_tld_match: int = 30
    disambiguation_score_company_in_domain: int = 20
    disambiguation_score_company_in_path: int = 10
    disambiguation_score_has_www: int = 5
    disambiguation_score_social_penalty: int = -50
    disambiguation_score_no_official_penalty: int = -10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()


# Convenience mapping: country code -> region for auto-deriving region from country
COUNTRY_TO_REGION: Dict[str, str] = {
    "IN": "India",
    "US": "USA",
    "GB": "UK",
    "DE": "Germany",
    "FR": "France",
    "JP": "Japan",
    "CN": "China",
    "AU": "Australia",
    "CA": "Canada",
    "BR": "Brazil",
    "NL": "Netherlands",
    "IT": "Italy",
    "ES": "Spain",
    "SG": "Singapore",
    "AE": "UAE",
}
