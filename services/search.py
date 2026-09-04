"""
Web search service for finding official company websites.

This module uses DuckDuckGo Search to find the official website
of a company and filters out non-official sources.
"""

import asyncio
import logging
import re
from difflib import SequenceMatcher
from typing import Optional, List

from ddgs import DDGS
from models import SearchResult, CompanyCandidate
from config import settings
from utils import (
    is_excluded_domain,
    is_valid_url,
    get_domain_from_url,
    classify_non_company_domain,
    guess_country_from_domain,
    strip_scheme,
    looks_like_url,
    ensure_scheme,
)


logger = logging.getLogger("company_intelligence.search")

# Generic suffixes that shouldn't count toward a name/domain relevance match
# (e.g. "Marvell Technology" vs domain "marvell" should match on "marvell",
# not get diluted by "technology" also needing to appear somewhere).
_COMPANY_SUFFIX_WORDS = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd",
    "limited", "llc", "plc", "group", "technologies", "technology",
    "holdings", "international", "global", "solutions",
}


def _name_tokens(text: str) -> set:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in tokens if t not in _COMPANY_SUFFIX_WORDS and len(t) > 1}


def rank_company_candidates(company_name: str, candidates: List[CompanyCandidate]) -> List[CompanyCandidate]:
    """
    Rank disambiguation candidates so the legitimate company sits first.

    Search-engine order is not reliable for this (a stock-quote page or
    news article can easily outrank the official site). Candidates are
    sorted by: (1) legitimate company profiles before non-company results,
    (2) how much the query's name overlaps the candidate's domain - the
    strongest signal of "this is the real site" - then (3) overall name
    similarity as a tiebreaker. Sort is stable, so ties keep their
    original (search-engine) relative order.
    """
    query_tokens = _name_tokens(company_name)

    def relevance(candidate: CompanyCandidate) -> float:
        domain_root = candidate.website.split("/", 1)[0].split(".")[0]
        domain_tokens = _name_tokens(domain_root.replace("-", " "))

        token_overlap = len(query_tokens & domain_tokens) / max(len(query_tokens), 1)
        name_similarity = SequenceMatcher(None, company_name.lower(), candidate.name.lower()).ratio()

        return token_overlap * 2 + name_similarity

    return sorted(candidates, key=lambda c: (c.type is not None, -relevance(c)))


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

    async def search_companies(self, company_name: str) -> tuple[List[CompanyCandidate], List[SearchResult]]:
        """
        Search for a company name and return every distinct entity found
        under that name, for disambiguation.

        Unlike search_official_website (which picks a single best guess),
        this surfaces name collisions - e.g. a company and an unrelated
        crypto token trading under the same name - so a caller can let the
        user pick the right one before calling /api/enrich.

        The same input also accepts a URL directly (e.g. someone pastes
        "marvell.com" instead of typing a name) - when it looks like one,
        search is skipped entirely and it comes back as the sole candidate,
        so a caller can always hit this endpoint first regardless of what
        the user typed.

        Args:
            company_name: Name (or URL) of the company to search for

        Returns:
            Tuple of (candidates deduplicated by domain, not yet ranked or
            truncated to the display limit - callers should apply
            rank_company_candidates() then slice; the raw search results
            they were built from, reusable for AI refinement so it doesn't
            need to re-query and risk a different result set)
        """
        if looks_like_url(company_name):
            logger.info(f"Input looks like a URL, skipping search: {company_name}")
            return [self._build_direct_url_candidate(company_name)], []

        logger.info(f"Searching for company candidates: {company_name}")

        results = await self._search(company_name)

        candidates: List[CompanyCandidate] = []
        seen_domains = set()

        for result in results:
            domain = get_domain_from_url(result.url)
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)

            candidates.append(self._build_candidate(company_name, result, domain))

        logger.info(f"Found {len(candidates)} distinct candidates for: {company_name}")
        return candidates, results

    def _build_direct_url_candidate(self, raw_input: str) -> CompanyCandidate:
        """Build a single candidate directly from a pasted URL, skipping search."""
        normalized = ensure_scheme(raw_input.strip())
        domain = get_domain_from_url(normalized) or strip_scheme(normalized)
        guessed_name = domain.split(".")[0].replace("-", " ").title() if domain else raw_input
        return CompanyCandidate(name=guessed_name or raw_input, website=domain or strip_scheme(normalized))

    def _build_candidate(self, company_name: str, result: SearchResult, domain: str) -> CompanyCandidate:
        """Build a single disambiguation candidate from a raw search result."""
        non_company_type = classify_non_company_domain(domain, result.url)

        if non_company_type:
            return CompanyCandidate(
                name=self._clean_candidate_name(result.title) or company_name,
                website=strip_scheme(result.url),
                type=non_company_type,
            )

        return CompanyCandidate(
            name=self._clean_candidate_name(result.title) or company_name,
            website=domain,
            country=guess_country_from_domain(domain),
            description=self._short_description(result.description),
        )

    def _clean_candidate_name(self, title: str) -> str:
        """Strip common title suffixes (' | Home', ' - Official Site', ...)."""
        if not title:
            return ""
        for separator in (" | ", " - ", " – ", " — "):
            if separator in title:
                title = title.split(separator)[0]
                break
        return title.strip()

    def _short_description(self, description: str, max_length: int = 200) -> Optional[str]:
        """Truncate a search snippet to a short description, or None if empty."""
        description = (description or "").strip()
        if not description:
            return None
        if len(description) <= max_length:
            return description
        return description[:max_length].rsplit(" ", 1)[0] + "..."

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
