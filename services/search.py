"""
Web search service for finding official company websites.

This module uses DuckDuckGo Search to find the official website
of a company and filters out non-official sources.
"""

import asyncio
import logging
from typing import Optional, List

from ddgs import DDGS
from models import SearchResult
from config import settings
from utils import is_excluded_domain, is_valid_url


logger = logging.getLogger("company_intelligence.search")


class SearchService:
    """Service for searching company websites."""

    def __init__(self):
        """Initialize the search service."""
        self.ddgs = DDGS()

    async def search_official_website(self, company_name: str) -> Optional[str]:
        """
        Search for the official website of a company.

        Args:
            company_name: Name of the company to search for

        Returns:
            Official website URL if found, None otherwise
        """
        logger.info(f"Searching for official website of: {company_name}")

        search_query = f"{company_name} official website"
        results = await self._search(search_query)

        # Filter for official website
        for result in results:
            if result.is_official and result.url:
                logger.info(f"Found official website: {result.url}")
                return result.url

        logger.warning(f"No official website found for: {company_name}")
        return None

    async def _search(self, query: str) -> List[SearchResult]:
        """
        Perform a web search and return results.

        Args:
            query: Search query string

        Returns:
            List of search results
        """
        try:
            # Run DuckDuckGo search in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.ddgs.text(
                    query,
                    max_results=settings.search_max_results
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
                    is_official=self._is_official_site(url, query)
                ))

            logger.info(f"Found {len(search_results)} valid search results")
            return search_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def _is_official_site(self, url: str, query: str) -> bool:
        """
        Determine if a URL is likely an official company website.

        Args:
            url: URL to evaluate
            query: Original search query

        Returns:
            True if likely an official site
        """
        # Exclude common non-official patterns
        exclude_patterns = [
            "wikipedia.org",
            "linkedin.com",
            "crunchbase.com",
            "glassdoor.com",
            "youtube.com",
            "facebook.com",
            "twitter.com",
            "reddit.com",
        ]

        url_lower = url.lower()
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False

        # Check if URL contains company-like elements
        # Official sites typically have the company name in the domain
        # or are clean .com domains
        if ".com" in url or ".org" in url or ".io" in url:
            return True

        return True
