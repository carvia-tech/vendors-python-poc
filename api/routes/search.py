"""
Company disambiguation search routes.

Provides:
- POST /api/search-companies  - Search a company name, return every distinct
                                 entity found under that name for the caller
                                 to disambiguate before enriching.
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException

from schemas.request import CompanySearchRequest
from models import CompanyCandidate
from api.dependencies import search_companies_pipeline

logger = logging.getLogger("company_intelligence.api.search")

router = APIRouter()


@router.post(
    "/search-companies",
    response_model=List[CompanyCandidate],
    response_model_exclude_none=True,
    summary="Search Companies",
    description=(
        "Search for a company name and return every distinct entity found under it "
        "(the real company plus any name collisions, e.g. an unrelated crypto token "
        "trading under the same name). Pick a candidate's `website` and pass it to "
        "POST /api/enrich to get full details."
    ),
    responses={
        200: {"description": "Disambiguation candidates (may be a single entry, or empty if nothing was found)"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def search_companies(request: CompanySearchRequest):
    """
    Search for companies matching a name.

    Args:
        request: CompanySearchRequest with company_name

    Returns:
        List of CompanyCandidate - legitimate company matches carry
        name/website/country/description; results that are NOT a company
        profile (a crypto price page, a news article, ...) instead carry
        name/website/type.
    """
    company_name = request.company_name.strip()

    if not company_name:
        raise HTTPException(
            status_code=422,
            detail="company_name is required and cannot be empty",
        )

    logger.info(f"Received company search request for: '{company_name}'")

    try:
        candidates = await search_companies_pipeline(company_name)
        logger.info(f"Found {len(candidates)} candidates for '{company_name}'")
        return candidates

    except Exception as e:
        logger.error(f"Unexpected error searching '{company_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )
