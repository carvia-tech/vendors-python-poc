"""
Public-review gathering service.

Collects what public review sites say about a company so a client can
judge whether it is worth working with. Two different kinds of site are
read, and the distinction matters:

  * employer sites (AmbitionBox, Glassdoor, Indeed) - what it is like to
    work *at* the company. High attrition or unpaid-salary complaints are
    a genuine vendor risk even though they are employee reviews.
  * B2B / client sites (Clutch, G2, Trustpilot, GoodFirms) - what it is
    like to work *with* them as a supplier: delivery quality, missed
    deadlines, billing disputes.

Review sites almost universally forbid scraping in their terms and block
datacenter IPs, so by default this reads only the public search-result
snippets that search engines already publish, and never fetches the review
pages themselves (see `settings.reviews_fetch_pages`). That yields
*indicative* sentiment, not verified review data, and the confidence field
on the result says how much material was actually found.
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Tuple

from ddgs import DDGS

from models import ReviewEvidence, ReviewSnippet
from config import settings
from utils import get_domain_from_url, looks_like_url, ensure_scheme


logger = logging.getLogger("company_intelligence.reviews")


# Ratings appear in snippets in a handful of shapes: "3.9/5",
# "rated 4.1 out of 5", "Rating: 4.2". Anything above 5 is not a
# five-point rating (it is a review count or a year) and is ignored.
_RATING_PATTERNS = [
    re.compile(r"(\d(?:\.\d)?)\s*/\s*5\b"),
    re.compile(r"(\d(?:\.\d)?)\s*out\s+of\s+5\b", re.IGNORECASE),
    re.compile(r"\brat(?:ed|ing)[:\s]+(\d(?:\.\d)?)\b", re.IGNORECASE),
]

# Cap per site so one chatty domain cannot crowd out every other source
# and skew the sentiment the LLM sees.
_MAX_SNIPPETS_PER_DOMAIN = 4


def parse_rating(text: str) -> Optional[float]:
    """
    Pull a five-point rating out of a snippet, or None if there isn't one.

    Deliberately conservative: a value outside 1-5 is not a rating on this
    scale, so it is discarded rather than clamped.
    """
    for pattern in _RATING_PATTERNS:
        match = pattern.search(text or "")
        if not match:
            continue
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        if 1.0 <= value <= 5.0:
            return value
    return None


# Legal-form and generic words carry no identifying signal, so they are
# dropped before deciding whether a snippet is about the right company.
_GENERIC_NAME_WORDS = {
    "private", "limited", "ltd", "pvt", "llp", "plc", "inc", "incorporated",
    "corporation", "corp", "company", "co", "group", "holdings",
    "international", "global", "solutions", "services", "technologies",
    "technology", "systems", "india",
}


def _significant_tokens(text: str) -> List[str]:
    """Word-split a name, dropping legal forms and one-character noise."""
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [t for t in tokens if t not in _GENERIC_NAME_WORDS and len(t) > 1]


def is_about_company(company_name: str, title: str, snippet: str, url: str) -> bool:
    """
    Decide whether a review snippet is about the company we asked for.

    Review sites are full of near-miss names, and a search for "Prolifics"
    readily returns Trustpilot reviews of "prolific.com" - a different
    company whose 4.5 rating would otherwise be averaged into this
    company's score. Matching is on whole tokens rather than substrings
    precisely so that "prolific" does not satisfy "prolifics".

    Every significant token of the name must appear. That is deliberately
    strict: for due diligence, dropping a genuine review is far cheaper
    than attributing a stranger's reviews to this vendor.
    """
    wanted = _significant_tokens(company_name)
    if not wanted:
        return False

    # The title and URL name the subject of the page; the snippet body is
    # excluded because it often mentions other companies in passing
    # ("compare with ...", "people also viewed ...").
    haystack = set(_significant_tokens(f"{title} {url.replace('/', ' ').replace('-', ' ')}"))
    return all(token in haystack for token in wanted)


class ReviewsService:
    """Gathers public-review evidence for a company."""

    def __init__(self):
        self.timeout = settings.reviews_timeout
        self.max_snippets = settings.reviews_max_snippets

    def _categorize(self, domain: str) -> Optional[str]:
        """
        Map a domain to the kind of review it carries, or None if the
        domain is not a review site we recognise.

        Matched by suffix so regional variants ("glassdoor.co.in",
        "in.indeed.com") resolve to the same category as the parent site.
        """
        for category, domains in (
            ("employer", settings.reviews_employer_domains),
            ("business", settings.reviews_business_domains),
            ("consumer", settings.reviews_consumer_domains),
        ):
            for known in domains:
                if domain == known or domain.endswith("." + known) or known in domain:
                    return category
        return None

    def _build_queries(self, company_name: str) -> List[str]:
        """
        Build the search queries used to surface review pages.

        Site-restricted queries are used for the highest-signal sites so
        their pages surface even when a generic "<name> reviews" search is
        dominated by the company's own marketing pages.
        """
        name = company_name.strip()
        return [
            f"{name} reviews",
            f"{name} employee reviews",
            f"{name} company reviews complaints",
            f"site:ambitionbox.com {name}",
            f"site:glassdoor.co.in {name} reviews",
            f"site:clutch.co {name}",
            f"site:trustpilot.com {name}",
            f"site:mouthshut.com {name}",
        ]

    async def gather(self, company_name: str) -> ReviewEvidence:
        """
        Gather review snippets for a company.

        Args:
            company_name: Name of the company to look up reviews for

        Returns:
            ReviewEvidence - empty (confidence "none") when nothing was
            found, which is normal for small or new vendors rather than an
            error.
        """
        if not settings.reviews_enabled:
            logger.info("Review gathering disabled by configuration")
            return ReviewEvidence()

        # A caller may pass a URL instead of a name (the same input field
        # accepts either) - reduce it to its brand word first, the same way
        # registry.py's _to_search_name() does. Left as-is, "carvia.tech"
        # would search "carvia.tech reviews" and require the literal token
        # "tech" to appear in every result, which guts recall for no reason.
        if looks_like_url(company_name):
            domain = get_domain_from_url(ensure_scheme(company_name))
            if domain:
                company_name = domain.split(".")[0].replace("-", " ")

        logger.info(f"Gathering reviews for: {company_name}")

        results = await asyncio.gather(
            *(self._search(query) for query in self._build_queries(company_name)),
            return_exceptions=True,
        )

        snippets: List[ReviewSnippet] = []
        seen_urls = set()
        per_domain: Dict[str, int] = {}

        for result in results:
            if isinstance(result, BaseException):
                logger.warning(f"A review search failed: {result}")
                continue

            for raw in result:
                url = raw.get("href") or ""
                domain = get_domain_from_url(url)
                if not domain or url in seen_urls:
                    continue

                category = self._categorize(domain)
                if not category:
                    continue

                if per_domain.get(domain, 0) >= _MAX_SNIPPETS_PER_DOMAIN:
                    continue

                title = raw.get("title") or ""
                body = raw.get("body") or ""

                if not is_about_company(company_name, title, body, url):
                    logger.debug(
                        f"Dropping snippet about a different company: {title[:70]!r} ({domain})"
                    )
                    continue

                seen_urls.add(url)
                per_domain[domain] = per_domain.get(domain, 0) + 1

                snippets.append(ReviewSnippet(
                    domain=domain,
                    category=category,
                    title=title.strip(),
                    snippet=body.strip(),
                    url=url,
                    rating=parse_rating(f"{title} {body}"),
                ))

                if len(snippets) >= self.max_snippets:
                    break

            if len(snippets) >= self.max_snippets:
                break

        evidence = ReviewEvidence(
            snippets=snippets,
            employer_rating=self._average_rating(snippets, "employer"),
            business_rating=self._average_rating(snippets, ("business", "consumer")),
            sources=sorted({s.url for s in snippets}),
            confidence=self._confidence(snippets),
        )

        logger.info(
            f"Review evidence for '{company_name}': {len(snippets)} snippet(s) "
            f"across {len(per_domain)} site(s), confidence={evidence.confidence}"
        )
        return evidence

    def _average_rating(self, snippets: List[ReviewSnippet], categories) -> Optional[float]:
        """Average the stated ratings for one or more categories, or None if none stated."""
        if isinstance(categories, str):
            categories = (categories,)

        ratings = [s.rating for s in snippets if s.category in categories and s.rating is not None]
        if not ratings:
            return None
        return round(sum(ratings) / len(ratings), 1)

    def _confidence(self, snippets: List[ReviewSnippet]) -> str:
        """
        Rate how much review material was found.

        Based on distinct sites rather than snippet count - five snippets
        from one site say much less than five snippets from five sites.
        """
        if not snippets:
            return "none"

        distinct_sites = len({s.domain for s in snippets})
        if distinct_sites >= 4 and len(snippets) >= 8:
            return "high"
        if distinct_sites >= 2:
            return "medium"
        return "low"

    async def _search(self, query: str) -> List[dict]:
        """
        Run one review search.

        A fresh DDGS per call rather than a shared long-lived client: the
        search backend rate-limits a persistent session far more
        aggressively, which matters here because one lookup fires several
        queries at once.
        """
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: DDGS().text(query, max_results=settings.search_max_results) or [],
            )
        except Exception as e:
            # Surfaced as a warning by the caller. A blocked or rate-limited
            # search must not take the whole enrichment down - reviews are
            # an enhancement to the profile, not a requirement.
            logger.warning(f"Review search failed for {query!r}: {e}")
            return []
