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


class Director(BaseModel):
    """A current director or key managerial person on the MCA registry."""

    name: str = Field(description="Director's full name as registered")
    designation: Optional[str] = Field(default=None, description="e.g. 'Director', 'Managing Director'")
    din: Optional[str] = Field(default=None, description="Director Identification Number")
    appointment_date: Optional[str] = Field(default=None, description="Date appointed (YYYY-MM-DD)")


class ReviewSnippet(BaseModel):
    """
    One public search-result snippet about a company from a review site.

    This is the raw evidence the LLM distils into points; keeping the url
    and domain on every snippet is what makes each resulting point
    attributable to a real source.
    """

    domain: str = Field(description="Review site domain, e.g. 'ambitionbox.com'")
    category: str = Field(description="'employer', 'business' or 'consumer'")
    title: str = Field(default="", description="Search result title")
    snippet: str = Field(default="", description="Search result snippet text")
    url: str = Field(description="URL of the review page")
    rating: Optional[float] = Field(default=None, description="Five-point rating stated in the snippet, if any")


class ReviewEvidence(BaseModel):
    """
    All review material gathered for a company, before LLM distillation.

    `confidence` reflects how many distinct sites were found, so a caller
    can tell "this vendor genuinely has a thin review footprint" apart from
    "we found plenty and it is mixed".
    """

    snippets: List[ReviewSnippet] = Field(default_factory=list, description="Raw review snippets")
    employer_rating: Optional[float] = Field(default=None, description="Mean rating across employer sites")
    business_rating: Optional[float] = Field(default=None, description="Mean rating across B2B/consumer sites")
    sources: List[str] = Field(default_factory=list, description="Distinct review URLs found")
    confidence: str = Field(default="none", description="'high', 'medium', 'low' or 'none'")


class ReviewPoint(BaseModel):
    """
    A single sentiment point distilled from public reviews.

    `source_domain` is mandatory and must be one of the review sites the
    gatherer actually saw. A point the LLM cannot attribute to a real
    source is dropped rather than shown - in a due-diligence context an
    invented review is worse than a missing one.
    """

    point: str = Field(description="The positive or negative point, one sentence")
    source_domain: str = Field(description="Review site the point came from, e.g. 'ambitionbox.com'")
    category: str = Field(
        default="general",
        description="What the point is about, e.g. 'management', 'delivery quality', 'payment terms'",
    )


class ReviewInsights(BaseModel):
    """
    Public-review sentiment for a company, split into positives and
    negatives so a client can weigh whether to work with them.

    Reviews are drawn from two different kinds of site and the distinction
    matters: employer sites (AmbitionBox, Glassdoor) say what it is like to
    work *at* the company, while B2B sites (Clutch, G2, Trustpilot) say what
    it is like to work *with* them as a vendor. Both are kept, each point
    tagged with the domain it came from.
    """

    positives: List[ReviewPoint] = Field(default_factory=list, description="Positive points from reviews")
    negatives: List[ReviewPoint] = Field(default_factory=list, description="Negative points / complaints")
    employer_rating: Optional[float] = Field(default=None, description="Average employer-site rating out of 5, if stated")
    business_rating: Optional[float] = Field(default=None, description="Average B2B/client-site rating out of 5, if stated")
    sources: List[str] = Field(default_factory=list, description="Review-site URLs the analysis drew on")
    confidence: str = Field(
        default="none",
        description="How much review material was actually found: 'high', 'medium', 'low' or 'none'",
    )
    summary: str = Field(default="Not Found", description="Two-sentence verdict on working with this company")


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

    # Company registry (MCA / ZaubaCorp) fields. Only Indian registered
    # companies have these, so a non-Indian company keeps the defaults.
    cin: str = Field(default="Not Found", description="Corporate Identification Number (21-char MCA CIN)")
    incorporation_date: str = Field(default="Not Found", description="Date of incorporation (YYYY-MM-DD)")
    company_age_years: Optional[int] = Field(default=None, description="Complete years since incorporation")
    registered_name: str = Field(
        default="Not Found",
        description="Registered name the CIN belongs to, so a wrong registry match is visible"
    )
    registered_email: str = Field(default="Not Found", description="Email registered with the MCA")
    directors: List[Director] = Field(default_factory=list, description="Current directors and KMP")

    # Public-review sentiment (employer + B2B sites). Empty when the
    # gatherer found no usable review material, which is common for
    # small or newly incorporated vendors.
    reviews: ReviewInsights = Field(default_factory=ReviewInsights, description="Positive/negative points from public reviews")


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


class RegistryRecord(BaseModel):
    """
    A company's entry in the Indian MCA registry, as surfaced by ZaubaCorp.

    `registered_name` is the name the CIN actually belongs to - it is kept
    (and surfaced on CompanyInfo) so that a bad name match is visible to
    the caller rather than silently attaching someone else's CIN.
    """

    registered_name: str = Field(description="Registered company name in the MCA registry")
    cin: str = Field(description="21-character Corporate Identification Number")
    incorporation_date: Optional[str] = Field(default=None, description="Date of incorporation (YYYY-MM-DD)")
    company_age_years: Optional[int] = Field(default=None, description="Complete years since incorporation")
    registered_email: Optional[str] = Field(default=None, description="Email registered with the MCA")
    directors: List[Director] = Field(default_factory=list, description="Current directors and KMP")
    source_url: str = Field(default="", description="ZaubaCorp page the record was read from")
