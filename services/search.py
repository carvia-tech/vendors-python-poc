"""
Web search service for finding official company websites.

This module uses DuckDuckGo Search to find the official website
of a company, with geo-context for disambiguating same-name companies.
"""

import asyncio
import logging
from typing import Optional, List, Tuple, Dict

from ddgs import DDGS
from models import SearchResult
from config import settings, COUNTRY_TO_REGION
from utils import is_excluded_domain, is_valid_url


logger = logging.getLogger("company_intelligence.search")


class SearchService:
    """Service for searching company websites with geo-aware disambiguation."""

    def __init__(self):
        """Initialize the search service."""
        self.ddgs = DDGS()

    async def search_official_website(
        self,
        company_name: str,
        region: Optional[str] = None,
        country: Optional[str] = None,
    ) -> Optional[str]:
        """
        Search for the official website of a company with geo-context.

        Uses multi-query strategy to find the best result:
        1. Primary: "{company_name} {region} official website" (if region exists)
        2. Secondary: "{company_name} {region}" (if region exists)
        3. Fallback: "{company_name} official website" (generic)

        Args:
            company_name: Name of the company to search for
            region: Optional geographic region (e.g., "India", "USA")
            country: Optional ISO country code (e.g., "IN", "US")

        Returns:
            Official website URL if found, None otherwise
        """
        logger.info(
            f"Searching for official website of: '{company_name}' "
            f"(region={region}, country={country})"
        )

        # Build search queries in priority order
        queries = self._build_geo_queries(company_name, region, country)

        # Try each query until we get a confident result
        all_candidates = []
        for query in queries:
            logger.info(f"Executing search query: '{query}'")
            results = await self._search(query)
            all_candidates.extend(results)

        if not all_candidates:
            logger.warning(f"No search results found for: {company_name}")
            return None

        # Use the disambiguator service to pick the best URL
        from services.disambiguator import DisambiguatorService
        disambiguator = DisambiguatorService()

        candidates_dict = [
            {"url": r.url, "title": r.title, "description": r.description}
            for r in all_candidates
        ]

        best_url, confidence, method = await disambiguator.resolve_best_url(
            company_name=company_name,
            candidates=candidates_dict,
            region=region,
            country=country,
        )

        if best_url:
            logger.info(
                f"Selected official website for '{company_name}': "
                f"{best_url} (confidence={confidence}, method={method})"
            )
            return best_url

        # Final fallback: first result
        logger.warning(
            f"Falling back to first result for '{company_name}': {all_candidates[0].url}"
        )
        return all_candidates[0].url if all_candidates else None

    def _build_geo_queries(
        self,
        company_name: str,
        region: Optional[str],
        country: Optional[str],
    ) -> List[str]:
        """
        Build search queries prioritized by geo-context.

        Returns queries in order of priority (most specific first).
        """
        queries = []

        # Derive the best location string
        location = region or ""
        if not location and country:
            location = COUNTRY_TO_REGION.get(country.upper(), country)

        if location:
            # Primary: region-specific official site search
            queries.append(f"{company_name} {location} official website")
            # Secondary: broader region search
            queries.append(f"{company_name} {location}")

        # Universal fallback
        queries.append(f"{company_name} official website")

        return queries

    async def search_top_candidates(
        self,
        company_name: str,
        region: Optional[str] = None,
        country: Optional[str] = None,
        max_candidates: int = 10,
    ) -> List[SearchResult]:
        """
        Search and return top candidate URLs with their metadata.

        This method returns raw candidates without disambiguation,
        useful for debugging or when you need all options.

        Args:
            company_name: Name of the company
            region: Optional geographic region
            country: Optional ISO country code
            max_candidates: Maximum number of candidates to return

        Returns:
            List of SearchResult objects
        """
        queries = self._build_geo_queries(company_name, region, country)

        all_candidates = []
        seen_urls = set()

        for query in queries:
            results = await self._search(query, max_results=max_candidates)
            for r in results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_candidates.append(r)

        return all_candidates[:max_candidates]

    async def _search(
        self,
        query: str,
        max_results: Optional[int] = None,
    ) -> List[SearchResult]:
        """
        Perform a web search and return results.

        Args:
            query: Search query string
            max_results: Max results (defaults to settings.search_max_results)

        Returns:
            List of search results
        """
        try:
            max_results = max_results or settings.search_max_results

            # Run DuckDuckGo search in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.ddgs.text(
                    query,
                    max_results=max_results,
                )
            )

            # Convert to SearchResult objects and filter
            search_results = []
            for result in results or []:
                url = result.get("href", "")
                if not is_valid_url(url):
                    continue

                if is_excluded_domain(url, settings.excluded_domains):
                    logger.debug(f"Excluding excluded domain: {url}")
                    continue

                search_results.append(SearchResult(
                    title=result.get("title", ""),
                    url=url,
                    description=result.get("body", ""),
                    is_official=True,  # Will be scored by DisambiguatorService
                ))

            logger.info(
                f"Search '{query}': found {len(search_results)} valid results"
            )
            return search_results

        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            return []

    def _is_official_site(self, url: str, query: str) -> bool:
        """
        Legacy method kept for backward compatibility.
        Always returns True; actual scoring is done by DisambiguatorService.

        Args:
            url: URL to evaluate
            query: Original search query

        Returns:
            Always True (scoring delegated to DisambiguatorService)
        """
        return True
