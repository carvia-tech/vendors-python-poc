"""
Enrichment API routes.

Provides endpoints for company information enrichment:
- GET  /api/health  - Health check
- POST /api/enrich  - Enrich company information
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from schemas.request import EnrichmentRequest
from schemas.response import (
    HealthResponse,
    EnrichmentResponse,
    ErrorResponse,
)
from api.dependencies import run_enrichment_pipeline
from config import settings

logger = logging.getLogger("company_intelligence.api.enrichment")

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check if the API service is running and healthy.",
)
async def health_check():
    """
    Health check endpoint.

    Returns:
        HealthResponse with service status and version info.
    """
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.post(
    "/enrich",
    response_model=EnrichmentResponse,
    summary="Enrich Company Information",
    description="Search, scrape, and analyze company information from their official website.",
    responses={
        200: {"model": EnrichmentResponse, "description": "Successful enrichment"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def enrich_company(request: EnrichmentRequest):
    """
    Enrich company information by:
    1. Searching for the official website
    2. Scraping homepage, about, and contact pages
    3. Extracting structured information
    4. Looking up the MCA company registry for CIN and age since
       incorporation (Indian registered companies only)
    5. Gathering public-review sentiment from employer and B2B review
       sites, distilled into positive and negative points
    6. Optionally analyzing with AI/LLM

    Args:
        request: EnrichmentRequest with company_name and optional api_key

    Returns:
        EnrichmentResponse containing company details and metadata
    """
    company_name = request.company_name.strip()

    if not company_name:
        raise HTTPException(
            status_code=422,
            detail="company_name is required and cannot be empty",
        )

    logger.info(f"Received enrichment request for: '{company_name}'")

    try:
        # Run the enrichment pipeline
        result = await run_enrichment_pipeline(
            company_name=company_name,
            website=request.website.strip() if request.website else None,
        )

        # Build the response
        response = EnrichmentResponse(
            success=result.metadata.status == "Success",
            data={
                "company": result.company.model_dump(),
                "metadata": result.metadata.model_dump(),
            },
            error=None if result.metadata.status == "Success" else result.company.overview,
        )

        logger.info(f"Enrichment completed for '{company_name}': status={result.metadata.status}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error enriching '{company_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )

