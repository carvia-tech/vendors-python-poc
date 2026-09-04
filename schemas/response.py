"""
Response schemas for the Company Intelligence Engine API.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class HealthResponse(BaseModel):
    """
    Response schema for the health check endpoint.

    Attributes:
        status: Service health status
        service: Service name
        version: Service version
        timestamp: Current server timestamp
    """

    status: str = Field(..., description="Service health status", examples=["ok"])
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    timestamp: str = Field(..., description="Current server timestamp")


class CompanyData(BaseModel):
    """
    Comprehensive company information data.

    This matches the JSON format consumed by the Java frontend.
    """

    name: str = Field(default="", description="Company name")
    website: str = Field(default="", description="Official website URL")
    industry: str = Field(default="Not Found", description="Industry sector")
    description: str = Field(default="", description="Company description")
    about_page: str = Field(default="Not Found", description="About page URL")
    contact_page: str = Field(default="Not Found", description="Contact page URL")
    careers_page: str = Field(default="Not Found", description="Careers page URL")
    emails: List[str] = Field(default_factory=list, description="Email addresses")
    phones: List[str] = Field(default_factory=list, description="Phone numbers")
    address: str = Field(default="Not Found", description="Company address")
    services: List[str] = Field(default_factory=list, description="Business services")
    technologies: List[str] = Field(default_factory=list, description="Technologies used")
    social_links: Dict[str, str] = Field(default_factory=dict, description="Social media links")
    overview: str = Field(default="Not Found", description="Company overview")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Infosys Limited",
                "website": "https://www.infosys.com",
                "industry": "Information Technology and Consulting",
                "description": "Infosys is a global technology company providing digital transformation, consulting, and outsourcing services.",
                "about_page": "https://www.infosys.com/about",
                "contact_page": "https://www.infosys.com/contact",
                "careers_page": "https://career.infosys.com",
                "emails": ["Not Found"],
                "phones": ["+91-80-2852-0261"],
                "address": "Electronics City, Hosur Road, Bengaluru, Karnataka, India",
                "services": [
                    "Digital Transformation",
                    "Cloud Services",
                    "Artificial Intelligence",
                    "Data Analytics",
                    "Cybersecurity",
                ],
                "technologies": [
                    "Azure",
                    "AWS",
                    "SAP",
                    "Salesforce",
                    "Java",
                    "Python",
                    "AI",
                    "Machine Learning",
                ],
                "social_links": {
                    "linkedin": "https://www.linkedin.com/company/infosys",
                    "youtube": "https://www.youtube.com/@Infosys",
                    "twitter": "https://twitter.com/Infosys",
                },
                "overview": "Infosys is an Indian multinational IT services company...",
            }
        }


class MetadataData(BaseModel):
    """
    Metadata about the company information retrieval.
    """

    source: str = Field(default="Official Website", description="Data source")
    confidence: int = Field(default=100, description="Confidence score (0-100)")
    retrieved_at: str = Field(..., description="When the data was retrieved")
    status: str = Field(..., description="Retrieval status")


class EnrichmentResponse(BaseModel):
    """
    Response schema for the /api/enrich endpoint.

    Attributes:
        success: Whether enrichment was successful
        data: Contains company and metadata objects
        error: Error message if failed
    """

    success: bool = Field(..., description="Whether the enrichment was successful")
    data: Optional[Dict[str, Any]] = Field(None, description="Company data and metadata")
    error: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "company": {
                        "name": "Infosys Limited",
                        "website": "https://www.infosys.com",
                        "industry": "Information Technology and Consulting",
                        "description": "Infosys is a global technology company...",
                        "about_page": "https://www.infosys.com/about",
                        "contact_page": "https://www.infosys.com/contact",
                        "careers_page": "https://career.infosys.com",
                        "emails": ["Not Found"],
                        "phones": ["+91-80-2852-0261"],
                        "address": "Electronics City, Hosur Road, Bengaluru, Karnataka, India",
                        "services": ["Digital Transformation", "Cloud Services"],
                        "technologies": ["Azure", "AWS", "SAP"],
                        "social_links": {
                            "linkedin": "https://www.linkedin.com/company/infosys"
                        },
                        "overview": "Infosys is an Indian multinational IT services company..."
                    },
                    "metadata": {
                        "source": "Official Website",
                        "confidence": 100,
                        "retrieved_at": "2026-07-21T10:30:00Z",
                        "status": "Success"
                    }
                },
                "error": None
            }
        }


class ErrorResponse(BaseModel):
    """
    Error response schema.
    """

    detail: str = Field(..., description="Error description")

