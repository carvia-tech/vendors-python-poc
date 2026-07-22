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

    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "Infosys",
                "api_key": "sk-your-api-key-here",
            }
        }

