"""
Dependency injection for FastAPI routes.

Provides shared service instances for the API endpoints.
"""

import logging

# Will be lazily initialized
_search_service = None
_extractor_service = None
_ai_service = None
_registry_service = None
_reviews_service = None
_services_initialized = False

logger = logging.getLogger("company_intelligence.api.dependencies")


def get_services():
    """
    Get or initialize all services lazily.

    Returns:
        Tuple of (SearchService, ExtractorService, AIAnalyzerService,
        RegistryService, ReviewsService)
    """
    global _search_service, _extractor_service, _ai_service, _registry_service, _reviews_service, _services_initialized

    if not _services_initialized:
        from services.search import SearchService
        from services.extractor import ExtractorService
        from services.ai_analyzer import AIAnalyzerService
        from services.registry import RegistryService
        from services.reviews import ReviewsService

        _search_service = SearchService()
        _extractor_service = ExtractorService()
        _ai_service = AIAnalyzerService()
        _registry_service = RegistryService()
        _reviews_service = ReviewsService()
        _services_initialized = True

        logger.info("Services initialized successfully")

    return _search_service, _extractor_service, _ai_service, _registry_service, _reviews_service


async def search_companies_pipeline(company_name: str):
    """
    Run the disambiguation search for a company name.

    Finds every distinct entity found under the given name (the official
    company plus any name collisions, e.g. an unrelated crypto token),
    optionally refined by AI when an LLM key is configured.

    Args:
        company_name: Name of the company to disambiguate

    Returns:
        List of CompanyCandidate
    """
    from config import settings
    from services.search import rank_company_candidates

    search_service, _extractor_service, ai_service, _registry_service, _reviews_service = get_services()

    candidates, raw_results = await search_service.search_companies(company_name)

    if settings.llm_api_key and candidates:
        ai_service.api_key = settings.llm_api_key
        candidates = await ai_service.classify_company_candidates(
            company_name, candidates, raw_results
        )

    # Rank after AI refinement (so demotions/promotions from AI classification
    # are reflected) and only then truncate to the display limit, so a
    # relevant match found later in the raw result set isn't dropped before
    # it gets a chance to rank above earlier, less relevant ones.
    candidates = rank_company_candidates(company_name, candidates)
    return candidates[:settings.disambiguation_max_candidates]


async def run_enrichment_pipeline(
    company_name: str,
    website: str = None,
    progress_callback=None
):
    """
    Run the full enrichment pipeline for a company.

    Args:
        company_name: Name of the company to analyze
        website: Optional pre-selected website (e.g. from search_companies_pipeline).
            When set, the search step is skipped and this site is scraped directly.
        progress_callback: Optional async callable(status, progress) for logging progress

    Returns:
        CompanyIntelligenceResponse object
    """
    from datetime import datetime, timezone
    from models import CompanyInfo, CompanyMetadata, CompanyIntelligenceResponse
    from services.scraper import ScraperService
    from config import settings
    from utils import ensure_scheme, is_valid_url

    search_service, extractor_service, ai_service, registry_service, reviews_service = get_services()

    log_steps = [
        (1, "Searching web for official website..."),
        (2, "Found official website, scraping homepage..."),
        (3, "Finding about & contact pages..."),
        (4, "Scraping additional pages..."),
        (5, "Extracting company information..."),
        (6, "Looking up company registry (CIN & age)..."),
        (7, "Gathering public reviews..."),
        (8, "AI analysis complete!"),
    ]

    async def _log(step: int, message: str):
        logger.info(f"[{step}/8] {message}")
        if progress_callback:
            await progress_callback(step, message)

    try:
        await _log(1, log_steps[0][1])

        if website:
            # Caller already picked a candidate (e.g. from /api/search-companies) -
            # skip the search and enrich that exact site.
            official_url = ensure_scheme(website.strip())
            if not is_valid_url(official_url):
                official_url = None
        else:
            # Step 1: Search for official website
            official_url = await search_service.search_official_website(company_name)

        if not official_url:
            await _log(8, "No official website found")
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

        # Step 6: Company registry lookup (CIN + age since incorporation).
        # Indian MCA-registered companies only - anything else legitimately
        # comes back empty and simply keeps the "Not Found" defaults.
        await _log(6, "Looking up company registry (CIN & age)...")
        registry_record = await registry_service.lookup(company_name)
        if registry_record:
            company_info.cin = registry_record.cin
            company_info.registered_name = registry_record.registered_name
            company_info.incorporation_date = registry_record.incorporation_date or "Not Found"
            company_info.company_age_years = registry_record.company_age_years
            company_info.registered_email = registry_record.registered_email or "Not Found"
            company_info.directors = registry_record.directors
            logger.info(
                f"Registry: {registry_record.registered_name} | CIN {registry_record.cin} | "
                f"age {registry_record.company_age_years} years | "
                f"{len(registry_record.directors)} director(s)"
            )
        else:
            logger.info(f"No registry record found for '{company_name}'")

        # Step 7: Public reviews. Employer sites say what it is like to work
        # at the company, B2B sites what it is like to work with them - both
        # feed the "is this a vendor worth onboarding" question. A vendor with
        # no review footprint legitimately comes back empty.
        await _log(7, "Gathering public reviews...")
        ai_service.api_key = settings.llm_api_key
        review_evidence = await reviews_service.gather(company_name)
        company_info.reviews = await ai_service.synthesize_reviews(
            company_name, review_evidence
        )
        logger.info(
            f"Reviews: {len(company_info.reviews.positives)} positive(s), "
            f"{len(company_info.reviews.negatives)} negative(s), "
            f"confidence={company_info.reviews.confidence}"
        )

        # Step 8: AI Analysis (using the server-configured API key only)
        if settings.llm_api_key:
            combined_content = extractor_service.combine_content_for_ai(
                homepage_content, about_content, contact_content
            )
            company_info = await ai_service.analyze_company(
                company_name, combined_content, company_info
            )
        else:
            company_info.industry = "Not Found"
            company_info.overview = "Not Found"

        await _log(8, "Analysis complete!")

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

