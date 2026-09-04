"""
Request schemas for the Company Intelligence Engine API.
"""

from typing import Optional

from pydantic import BaseModel, Field


class EnrichmentRequest(BaseModel):
    """
    Request schema for the /api/enrich endpoint.

    Attributes:
        company_name: Name of the company to enrich
        website: Optional pre-selected website (e.g. from /api/search-companies).
            When set, enrichment scrapes this site directly instead of
            re-searching for the official website.
    """

    company_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name of the company to look up",
        examples=["Infosys", "Microsoft", "Google"],
    )
    website: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Pre-selected website to enrich directly, from a prior /api/search-companies candidate",
    )
    class Config:
        # Reject accidental credential fields instead of silently accepting them.
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "company_name": "Infosys",
            }
        }


class CompanySearchRequest(BaseModel):
    """
    Request schema for the /api/search-companies endpoint.

    Attributes:
        company_name: Name of the company to disambiguate
    """

    company_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name of the company to search for",
        examples=["Marvell Technology", "Infosys"],
    )

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "company_name": "Marvell Technology",
            }
        }

