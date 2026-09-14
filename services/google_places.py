"""
Google Reviews via the Google Places API.

Every other review source in this pipeline works by reading public
search-result snippets, because scraping the review sites themselves is
against their terms. Google reviews don't fit that pattern - Google's own
review pages aren't reliably indexed with rating snippets the way a
Glassdoor or Trustpilot page is - so this instead calls Google's licensed
Places API directly, which also happens to return genuine review text
rather than a landing-page blurb.

Optional: only runs when GOOGLE_PLACES_API_KEY is configured. Without one,
find_reviews() returns None and the rest of review gathering is unaffected.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from config import settings
from utils import ensure_scheme, get_domain_from_url


logger = logging.getLogger("company_intelligence.google_places")


class GooglePlacesService:
    """Looks up a company's Google rating and reviews via the Places API."""

    def __init__(self):
        self.api_key = settings.google_places_api_key
        self.base_url = settings.google_places_base_url
        self.timeout = settings.google_places_timeout

    async def find_reviews(
        self,
        company_name: str,
        website: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve a company to its Google Place and return its aggregate
        rating, review count, and a sample of individual reviews.

        Args:
            company_name: Company name to search for
            website: Known official website, if any. Used to verify Places
                resolved the right business - Google's text search is
                generally reliable, but attaching a stranger's rating to
                this vendor on a bad match would be worse than finding
                nothing, so a disagreeing website rejects the match.

        Returns:
            {"name", "rating", "user_ratings_total", "maps_url", "reviews": [...]}
            or None if disabled, no match was found, or the match didn't verify.
        """
        if not self.api_key:
            return None

        try:
            place_id, _name = await self._find_place(company_name)
            if not place_id:
                logger.info(f"No Google Place found for '{company_name}'")
                return None

            details = await self._get_place_details(place_id)
            if not details:
                return None

            if not self._verify_match(website, details.get("website")):
                logger.info(
                    f"Google Place '{details.get('name')}' website doesn't match "
                    f"the known site for '{company_name}' - skipping to avoid a wrong attribution"
                )
                return None

            reviews = [
                {
                    "author": review.get("author_name", "Anonymous"),
                    "rating": review.get("rating"),
                    "text": (review.get("text") or "").strip(),
                    "relative_time": review.get("relative_time_description", ""),
                }
                for review in (details.get("reviews") or [])[:settings.google_places_max_reviews]
            ]

            logger.info(
                f"Google Places match for '{company_name}': {details.get('name')} "
                f"rated {details.get('rating')} ({details.get('user_ratings_total', 0)} reviews)"
            )

            return {
                "name": details.get("name", company_name),
                "rating": details.get("rating"),
                "user_ratings_total": details.get("user_ratings_total"),
                "maps_url": details.get("url", ""),
                "reviews": reviews,
            }

        except Exception as e:
            # A Google lookup failure must never take down the wider review
            # gathering - it is one source among several.
            logger.error(f"Google Places lookup failed for '{company_name}': {e}", exc_info=True)
            return None

    def _verify_match(self, known_website: Optional[str], found_website: Optional[str]) -> bool:
        """
        Cross-check the resolved Place's own website against the company's
        known site, when both are available - the strongest signal this is
        actually the right business. Either side being unknown is allowed
        through rather than rejected, since Places' text search is already
        fairly reliable at entity resolution on its own.
        """
        if not known_website or not found_website:
            return True

        known_domain = get_domain_from_url(ensure_scheme(known_website))
        found_domain = get_domain_from_url(ensure_scheme(found_website))
        if not known_domain or not found_domain:
            return True

        return known_domain == found_domain

    async def _find_place(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """Resolve a text query to a place_id via Find Place From Text."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/findplacefromtext/json",
                params={
                    "input": query,
                    "inputtype": "textquery",
                    "fields": "place_id,name",
                    "key": self.api_key,
                },
            )
            response.raise_for_status()
            data = response.json()

        status = data.get("status")
        if status != "OK" or not data.get("candidates"):
            if status not in ("OK", "ZERO_RESULTS"):
                logger.warning(f"Google Places Find Place returned {status}: {data.get('error_message', '')}")
            return None, None

        best = data["candidates"][0]
        return best.get("place_id"), best.get("name")

    async def _get_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        """Fetch rating, review count, sample reviews, and website for a place."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/details/json",
                params={
                    "place_id": place_id,
                    "fields": "name,rating,user_ratings_total,reviews,url,website",
                    "key": self.api_key,
                },
            )
            response.raise_for_status()
            data = response.json()

        status = data.get("status")
        if status != "OK":
            logger.warning(f"Google Places Details returned {status}: {data.get('error_message', '')}")
            return None

        return data.get("result")
