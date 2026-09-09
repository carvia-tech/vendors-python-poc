"""
Response schemas for the Company Intelligence Engine API.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from models import Director, ReviewInsights


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

    # Company registry (MCA / ZaubaCorp) fields - Indian registered
    # companies only; others keep the defaults.
    cin: str = Field(default="Not Found", description="Corporate Identification Number (21-char MCA CIN)")
    incorporation_date: str = Field(default="Not Found", description="Date of incorporation (YYYY-MM-DD)")
    company_age_years: Optional[int] = Field(default=None, description="Complete years since incorporation")
    registered_name: str = Field(default="Not Found", description="Registered name the CIN belongs to")
    registered_email: str = Field(default="Not Found", description="Email registered with the MCA")
    directors: List[Director] = Field(default_factory=list, description="Current directors and KMP")

    # Public-review sentiment, split into positives and negatives so a
    # client can weigh whether to work with the company. Empty when no
    # review footprint was found.
    reviews: ReviewInsights = Field(default_factory=ReviewInsights, description="Positive/negative points from public reviews")

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
                "cin": "L85110KA1981PLC013115",
                "incorporation_date": "1981-07-02",
                "company_age_years": 45,
                "registered_name": "INFOSYS LIMITED",
                "registered_email": "Manikantha_AGS@infosys.com",
                "directors": [
                    {
                        "name": "NANDAN MOHAN NILEKANI",
                        "designation": "Director",
                        "din": "00041245",
                        "appointment_date": "2017-10-07",
                    }
                ],
                "reviews": {
                    "positives": [
                        {
                            "point": "Employees consistently rate the learning and training opportunities highly.",
                            "source_domain": "ambitionbox.com",
                            "category": "training",
                        }
                    ],
                    "negatives": [
                        {
                            "point": "Repeated complaints about below-market salary revisions.",
                            "source_domain": "ambitionbox.com",
                            "category": "compensation",
                        }
                    ],
                    "employer_rating": 3.8,
                    "business_rating": None,
                    "sources": ["https://www.ambitionbox.com/reviews/infosys-reviews"],
                    "confidence": "medium",
                    "summary": "The review record supports working with this company on delivery capability. The main caveat is attrition risk implied by compensation complaints.",
                },
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
                        "overview": "Infosys is an Indian multinational IT services company...",
                        "cin": "L85110KA1981PLC013115",
                        "incorporation_date": "1981-07-02",
                        "company_age_years": 45,
                        "registered_name": "INFOSYS LIMITED",
                        "registered_email": "Manikantha_AGS@infosys.com",
                        "directors": [
                            {
                                "name": "NANDAN MOHAN NILEKANI",
                                "designation": "Director",
                                "din": "00041245",
                                "appointment_date": "2017-10-07"
                            }
                        ]
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

