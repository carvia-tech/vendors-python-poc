"""
Request schemas for the Company Intelligence Engine API.
"""

from pydantic import BaseModel, Field


class EnrichmentRequest(BaseModel):
    """
    Request schema for the /api/enrich endpoint.

    Attributes:
        company_name: Name of the company to enrich
    """

    company_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name of the company to look up",
        examples=["Infosys", "Microsoft", "Google"],
    )
    class Config:
        # Reject accidental credential fields instead of silently accepting them.
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "company_name": "Infosys",
            }
        }

