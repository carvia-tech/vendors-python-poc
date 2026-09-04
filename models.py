"""
Pydantic models for the Company Intelligence Engine.

This module defines all data models used throughout the application,
ensuring type safety and validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, timezone
from enum import Enum


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    SUCCESS = "Success"
    FAILED = "Failed"


class SocialLinks(BaseModel):
    """Social media links."""

    linkedin: Optional[str] = None
    twitter: Optional[str] = None
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    youtube: Optional[str] = None
    github: Optional[str] = None


class CompanyInfo(BaseModel):
    """Structured company information."""

    name: str = Field(default="", description="Company name")
    industry: str = Field(default="Not Found", description="Industry sector")
    description: str = Field(default="", description="Company description")
    website: str = Field(default="", description="Official website URL")
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


class CompanyMetadata(BaseModel):
    """Metadata about the company information retrieval."""

    source: str = Field(default="Official Website", description="Data source")
    confidence: int = Field(default=100, description="Confidence score (0-100)")
    retrieved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = Field(default=TaskStatus.SUCCESS.value, description="Retrieval status")


class CompanyIntelligenceResponse(BaseModel):
    """Complete company intelligence response."""

    company: CompanyInfo
    metadata: CompanyMetadata


class ScrapedContent(BaseModel):
    """Content scraped from a webpage."""

    url: str
    title: str = ""
    description: str = ""
    headings: List[str] = Field(default_factory=list)
    paragraphs: List[str] = Field(default_factory=list)
    links: List[str] = Field(default_factory=list)
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    raw_text: str = ""


class SearchResult(BaseModel):
    """Web search result."""

    title: str
    url: str
    description: str
    is_official: bool = False


class CompanyCandidate(BaseModel):
    """
    A single disambiguation candidate returned by /api/search-companies.

    `type` is populated only when the result is NOT a company profile
    (e.g. a crypto price page or news article reusing the same name) -
    such candidates should not be sent to /api/enrich. Legitimate company
    candidates instead carry `country`/`description` and omit `type`.
    """

    name: str = Field(description="Company or entity name")
    website: str = Field(description="Website (or page path, for non-company results) to enrich")
    country: Optional[str] = Field(default=None, description="Country of the company, if determinable")
    description: Optional[str] = Field(default=None, description="Short description of the company")
    type: Optional[str] = Field(default=None, description="Set when this is NOT a company profile, e.g. 'Crypto price page'")
