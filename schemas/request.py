"""
Request schemas for the Company Intelligence Engine API.
"""

from pydantic import BaseModel, Field
from typing import Optional


class EnrichmentRequest(BaseModel):
    """
    Request schema for the /api/enrich endpoint.

    Attributes:
        company_name: Name of the company to enrich
        api_key: Optional OpenAI API key for AI-powered analysis
        region: Optional geographic region/territory to disambiguate same-name companies
                (e.g., "India", "USA", "Europe")
        country: Optional ISO country code for precise geo-targeting
                 (e.g., "IN", "US", "GB", "DE")
    """

    company_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name of the company to look up",
        examples=["Infosys", "Microsoft", "Google"],
    )
    api_key: Optional[str] = Field(
        None,
        description="Optional OpenAI API key for AI-powered enrichment",
        examples=["sk-..."],
    )
    region: Optional[str] = Field(
        None,
        max_length=100,
        description="Geographic region for company disambiguation (e.g., 'India', 'USA', 'Europe')",
        examples=["India", "USA", "Europe"],
    )
    country: Optional[str] = Field(
        None,
        max_length=2,
        min_length=2,
        description="ISO 3166-1 alpha-2 country code for precise geo-targeting",
        examples=["IN", "US", "GB", "DE"],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "Amazon",
                "api_key": "sk-your-api-key-here",
                "region": "India",
                "country": "IN",
            }
        }

