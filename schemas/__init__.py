"""
Schemas package for the Company Intelligence Engine API.

Contains request and response schemas for the FastAPI endpoints.
"""

from .request import EnrichmentRequest
from .response import HealthResponse, EnrichmentResponse, ErrorResponse

__all__ = [
    "EnrichmentRequest",
    "HealthResponse",
    "EnrichmentResponse",
    "ErrorResponse",
]

