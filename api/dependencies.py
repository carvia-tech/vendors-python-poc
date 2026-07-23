"""
Dependency injection for FastAPI routes.

Provides shared service instances for the API endpoints.
"""

import logging
from typing import Optional

# Will be lazily initialized
_search_service = None
_extractor_service = None
_ai_service = None
_services_initialized = False

logger = logging.getLogger("company_intelligence.api.dependencies")


def get_services():
    """
    Get or initialize all services lazily.

    Returns:
        Tuple of (SearchService, ExtractorService, AIAnalyzerService)
    """
    global _search_service, _extractor_service, _ai_service, _services_initialized

    if not _services_initialized:
        from services.search import SearchService
        from services.extractor import ExtractorService
        from services.ai_analyzer import AIAnalyzerService

        _search_service = SearchService()
        _extractor_service = ExtractorService()
        _ai_service = AIAnalyzerService()
        _services_initialized = True

        logger.info("Services initialized successfully")

    return _search_service, _extractor_service, _ai_service


async def run_enrichment_pipeline(
    company_name: str,
    llm_api_key: Optional[str] = None,
    region: Optional[str] = None,
    country: Optional[str] = None,
    progress_callback=None
):
    """
    Run the full enrichment pipeline for a company.

    Args:
        company_name: Name of the company to analyze
        llm_api_key: Optional OpenAI API key for AI analysis
        region: Optional geographic region for same-name disambiguation (e.g., "India")
        country: Optional ISO country code for geo-targeting (e.g., "IN")
        progress_callback: Optional async callable(status, progress) for logging progress

    Returns:
        CompanyIntelligenceResponse object
    """
    from datetime import datetime, timezone
    from models import CompanyInfo, CompanyMetadata, CompanyIntelligenceResponse
    from services.scraper import ScraperService
    from config import settings

    search_service, extractor_service, ai_service = get_services()

    log_steps = [
        (1, "Searching web for official website..."),
        (2, "Found official website, scraping homepage..."),
        (3, "Finding about & contact pages..."),
        (4, "Scraping additional pages..."),
        (5, "Extracting company information..."),
        (6, "AI analysis complete!"),
    ]

    async def _log(step: int, message: str):
        logger.info(f"[{step}/6] {message}")
        if progress_callback:
            await progress_callback(step, message)

    try:
        await _log(1, log_steps[0][1])

        # Step 1: Search for official website with geo-context
        official_url = await search_service.search_official_website(
            company_name,
            region=region,
            country=country,
        )

        if not official_url:
            await _log(6, "No official website found")
            company_info = CompanyInfo(
                name=company_name,
                overview="Analysis failed: No official website found"
            )
            metadata = CompanyMetadata(
                source="Analysis Failed",
                confidence=0,
                status="Failed"
            )
            return CompanyIntelligenceResponse(company=company_info, metadata=metadata)

        await _log(2, f"Found: {official_url}")

        # Step 2-3: Scrape homepage and find special pages
        async with ScraperService() as scraper:
            await _log(3, "Scraping homepage...")
            homepage_content = await scraper.scrape_page(official_url)
            special_pages = await scraper.find_special_pages(official_url)

            await _log(4, "Scraping additional pages...")
            pages_to_scrape = []
            about_url = special_pages.get("about")
            contact_url = special_pages.get("contact")

            if about_url and about_url != "Not Found":
                pages_to_scrape.append(about_url)
            if contact_url and contact_url != "Not Found":
                pages_to_scrape.append(contact_url)

            scraped_pages = await scraper.scrape_multiple_pages(pages_to_scrape)
            about_content = scraped_pages.get(about_url) if about_url in scraped_pages else None
            contact_content = scraped_pages.get(contact_url) if contact_url in scraped_pages else None

        # Step 5: Extract info
        await _log(5, "Extracting company information...")
        company_info = extractor_service.extract_company_info(
            homepage_content=homepage_content,
            about_content=about_content,
            contact_content=contact_content,
            careers_content=None,
            special_pages=special_pages
        )

        # Step 6: AI Analysis (if API key provided)
        api_key = llm_api_key or settings.llm_api_key
        if api_key:
            # Temporarily set the API key for the AI service
            ai_service.api_key = api_key
            combined_content = extractor_service.combine_content_for_ai(
                homepage_content, about_content, contact_content
            )
            company_info = await ai_service.analyze_company(
                company_name, combined_content, company_info
            )
        else:
            company_info.industry = "Not Found"
            company_info.overview = "Not Found"

        await _log(6, "Analysis complete!")

        metadata = CompanyMetadata(
            source="Official Website",
            confidence=100,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            status="Success"
        )

        return CompanyIntelligenceResponse(company=company_info, metadata=metadata)

    except Exception as e:
        logger.error(f"Enrichment pipeline failed for '{company_name}': {e}", exc_info=True)
        company_info = CompanyInfo(
            name=company_name,
            overview=f"Analysis failed: {str(e)}"
        )
        metadata = CompanyMetadata(
            source="Analysis Failed",
            confidence=0,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            status="Failed"
        )
        return CompanyIntelligenceResponse(company=company_info, metadata=metadata)

