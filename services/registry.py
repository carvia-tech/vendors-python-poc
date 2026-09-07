"""
Company registry lookup service (Indian MCA data via ZaubaCorp).

This module resolves a company name to its MCA registry entry and reads
back the two facts the enrichment pipeline cares about: the company's CIN
(Corporate Identification Number) and how many years it has existed since
incorporation.

Only Indian, MCA-registered companies appear in this registry, so a
non-Indian company (Stripe, Google, ...) legitimately resolves to nothing
and the lookup returns None rather than guessing.
"""

import asyncio
import logging
import re
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Optional, List, Tuple
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

from models import RegistryRecord
from config import settings
from utils import looks_like_url, get_domain_from_url, ensure_scheme


logger = logging.getLogger("company_intelligence.registry")


# A CIN is a fixed 21-character code, e.g. L85110KA1981PLC013115:
#   L      listing status (L listed / U unlisted)
#   85110  5-digit industry code
#   KA     2-letter state code
#   1981   4-digit year of incorporation
#   PLC    3-letter ownership class
#   013115 6-digit registration number
CIN_PATTERN = re.compile(r"[LU]\d{5}[A-Z]{2}(\d{4})[A-Z]{3}\d{6}", re.IGNORECASE)

# Legal-form words that carry no identifying signal - "INFOSYS" and
# "INFOSYS LIMITED" are the same company, so these are dropped before any
# name comparison.
_LEGAL_SUFFIX_WORDS = {
    "private", "limited", "ltd", "pvt", "llp", "plc",
    "inc", "incorporated", "corporation", "corp", "company", "co",
}


def normalize_company_tokens(name: str) -> List[str]:
    """
    Reduce a company name to its identifying tokens, dropping legal-form
    words so "Infosys", "Infosys Ltd" and "INFOSYS LIMITED" all compare equal.
    """
    tokens = re.findall(r"[a-z0-9]+", (name or "").lower())
    return [t for t in tokens if t not in _LEGAL_SUFFIX_WORDS]


def name_match_score(query: str, candidate: str) -> float:
    """
    Score how confidently a registry entry is the company being asked about.

    Deliberately strict. A registry search for a brand name returns many
    unrelated companies that merely contain the word - "Stripe" surfaces
    STRIPE IMPEX PRIVATE LIMITED, "Flipkart" surfaces FLIPKART FOUNDATION -
    and attaching one of those CINs to the wrong company is worse than
    reporting nothing. Only an exact match on identifying tokens is
    treated as confident (1.0); everything else scores below the accept
    threshold and is rejected by lookup().

    Returns:
        1.0 for an exact identifying-token match, otherwise a similarity
        ratio in [0, 1) used only for ordering/diagnostics
    """
    query_tokens = normalize_company_tokens(query)
    candidate_tokens = normalize_company_tokens(candidate)

    if not query_tokens or not candidate_tokens:
        return 0.0
    if query_tokens == candidate_tokens:
        return 1.0

    return SequenceMatcher(None, " ".join(query_tokens), " ".join(candidate_tokens)).ratio()


# Below this, a candidate is not accepted. Set to exact-match-only on
# purpose (see name_match_score).
MATCH_ACCEPT_THRESHOLD = 1.0


def years_since(incorporation_date: str, today: Optional[date] = None) -> Optional[int]:
    """
    Complete years elapsed since a YYYY-MM-DD incorporation date.

    Computed here rather than read off the registry page, because
    ZaubaCorp's own "Age of Company" string is unreliable - it renders
    values like "5 years, -1 months, 25 days".

    Returns:
        Whole years elapsed, or None if the date can't be parsed or is in
        the future
    """
    if not incorporation_date:
        return None

    try:
        incorporated = datetime.strptime(incorporation_date.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        logger.debug(f"Unparseable incorporation date: {incorporation_date!r}")
        return None

    today = today or date.today()
    if incorporated > today:
        logger.warning(f"Incorporation date is in the future, ignoring: {incorporation_date}")
        return None

    # Standard "birthday" arithmetic: drop a year if the anniversary
    # hasn't come round yet this year.
    return today.year - incorporated.year - (
        (today.month, today.day) < (incorporated.month, incorporated.day)
    )


class RegistryService:
    """Service for looking up a company's CIN and age in the MCA registry."""

    def __init__(self):
        """Initialize the registry service."""
        self.base_url = settings.registry_base_url.rstrip("/")
        self.timeout = settings.registry_timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    async def lookup(self, company_name: str) -> Optional[RegistryRecord]:
        """
        Resolve a company name to its MCA registry record.

        Args:
            company_name: Company name to look up. A URL is accepted too
                (the pipeline's input may be one) and is reduced to its
                domain's brand word first.

        Returns:
            RegistryRecord when a confident match is found, otherwise None -
            which is the correct answer for any non-Indian company, and the
            safe answer when only weak name matches exist.
        """
        if not settings.registry_enabled:
            logger.debug("Registry lookup disabled by settings")
            return None

        search_name = self._to_search_name(company_name)
        if not search_name:
            return None

        logger.info(f"Registry lookup for: {search_name}")

        try:
            candidates = await self._find_candidates(search_name)
            if not candidates:
                logger.info(f"No registry candidates found for '{search_name}'")
                return None

            best_name, best_url, best_cin = max(
                candidates, key=lambda c: name_match_score(search_name, c[0])
            )
            score = name_match_score(search_name, best_name)

            if score < MATCH_ACCEPT_THRESHOLD:
                # Rejecting here is the point: the registry is full of
                # unrelated companies sharing a brand word.
                logger.info(
                    f"No confident registry match for '{search_name}' "
                    f"(closest: '{best_name}' at {score:.2f}) - reporting nothing"
                )
                return None

            logger.info(f"Matched registry entry '{best_name}' (CIN {best_cin})")
            return await self._build_record(best_name, best_url, best_cin)

        except Exception as e:
            # A registry miss must never fail the wider enrichment run.
            logger.error(f"Registry lookup failed for '{company_name}': {e}", exc_info=True)
            return None

    def _to_search_name(self, company_name: str) -> str:
        """
        Turn the pipeline's input into something worth searching the
        registry for - callers may pass a URL ("infosys.com") instead of
        a name, in which case the domain's brand word is used.
        """
        company_name = (company_name or "").strip()
        if not company_name:
            return ""

        if looks_like_url(company_name):
            domain = get_domain_from_url(ensure_scheme(company_name))
            if domain:
                return domain.split(".")[0].replace("-", " ")

        return company_name

    async def _find_candidates(self, search_name: str) -> List[Tuple[str, str, str]]:
        """
        Find registry entries matching a name.

        ZaubaCorp's own search is tried first (it is the authoritative
        index and returns exact matches at the top); a web search
        restricted to the site is the fallback for when that endpoint is
        unavailable or its markup changes.

        Returns:
            List of (registered_name, page_url, cin) tuples
        """
        candidates = await self._search_registry_site(search_name)
        if candidates:
            return candidates

        logger.info("Registry site search returned nothing, falling back to web search")
        return await self._search_via_web(search_name)

    async def _search_registry_site(self, search_name: str) -> List[Tuple[str, str, str]]:
        """Query ZaubaCorp's own company search and parse the result links."""
        url = f"{self.base_url}/companysearchresults/{quote(search_name.upper())}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return self._parse_candidate_links(response.text, url)

        except httpx.HTTPError as e:
            logger.warning(f"Registry site search failed for '{search_name}': {e}")
            return []

    async def _search_via_web(self, search_name: str) -> List[Tuple[str, str, str]]:
        """
        Fall back to a site-restricted web search.

        Result URLs carry the CIN and titles carry the registered name, so
        the same parsing and matching applies as for the site's own search.
        """
        try:
            from ddgs import DDGS

            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: DDGS().text(f"site:zaubacorp.com {search_name}", max_results=10),
            )
        except Exception as e:
            logger.warning(f"Web-search fallback failed for '{search_name}': {e}")
            return []

        candidates: List[Tuple[str, str, str]] = []
        seen_cins = set()

        for result in results or []:
            url = result.get("href", "")
            match = CIN_PATTERN.search(url)
            if not match:
                continue

            cin = match.group(0).upper()
            if cin in seen_cins:
                continue
            seen_cins.add(cin)

            # Titles look like "INFOSYS LIMITED | ZaubaCorp" - keep the name.
            name = (result.get("title") or "").split("|")[0].strip()
            if name:
                candidates.append((name, url, cin))

        logger.info(f"Web-search fallback found {len(candidates)} registry candidates")
        return candidates

    def _parse_candidate_links(self, html: str, base_url: str) -> List[Tuple[str, str, str]]:
        """
        Pull (name, url, cin) out of a registry search-results page.

        Every company link embeds the CIN in its URL, which is what makes
        the CIN readable without fetching each result.
        """
        soup = BeautifulSoup(html, "html.parser")

        candidates: List[Tuple[str, str, str]] = []
        seen_cins = set()

        for anchor in soup.find_all("a", href=True):
            match = CIN_PATTERN.search(anchor["href"])
            if not match:
                continue

            # The same company is linked more than once per row (name link
            # plus an icon link with no text); keep the one carrying the name.
            name = anchor.get_text(" ", strip=True)
            if not name:
                continue

            cin = match.group(0).upper()
            if cin in seen_cins:
                continue
            seen_cins.add(cin)

            candidates.append((name, urljoin(base_url, anchor["href"]), cin))

            if len(candidates) >= settings.registry_max_candidates:
                break

        logger.info(f"Registry site search found {len(candidates)} candidates")
        return candidates

    async def _build_record(self, name: str, url: str, cin: str) -> RegistryRecord:
        """
        Fetch a company's registry page and assemble its record.

        The CIN is already known from the URL, so a failure to fetch or
        parse the page still yields a usable record - the incorporation
        year encoded in the CIN itself covers the age.
        """
        incorporation_date = await self._fetch_incorporation_date(url)
        age = years_since(incorporation_date) if incorporation_date else None

        if incorporation_date:
            self._warn_on_year_mismatch(cin, incorporation_date)
        else:
            # No date on the page - fall back to the year inside the CIN,
            # which is enough for an age in whole years.
            age = self._age_from_cin(cin)
            logger.info(f"No incorporation date on page, derived age from CIN: {age}")

        return RegistryRecord(
            registered_name=name,
            cin=cin,
            incorporation_date=incorporation_date,
            company_age_years=age,
            source_url=url,
        )

    async def _fetch_incorporation_date(self, url: str) -> Optional[str]:
        """Fetch a registry page and read its 'Date of Incorporation' field."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            return self._extract_labelled_value(soup, "Date of Incorporation")

        except httpx.HTTPError as e:
            logger.warning(f"Could not fetch registry page {url}: {e}")
            return None

    def _extract_labelled_value(self, soup: BeautifulSoup, label: str) -> Optional[str]:
        """
        Read a value from the registry page's label/value rows, which are
        laid out as `<span>Date of Incorporation</span><label>1981-07-02</label>`.
        """
        for span in soup.find_all("span"):
            if span.get_text(strip=True).lower() != label.lower():
                continue

            value_tag = span.find_next("label")
            if value_tag:
                value = value_tag.get_text(" ", strip=True)
                if value and value.lower() not in ("not available", "-"):
                    return value

        logger.debug(f"Label not found on registry page: {label}")
        return None

    def _age_from_cin(self, cin: str) -> Optional[int]:
        """Derive age from the 4-digit incorporation year embedded in the CIN."""
        match = CIN_PATTERN.search(cin)
        if not match:
            return None

        year = int(match.group(1))
        age = date.today().year - year
        return age if age >= 0 else None

    def _warn_on_year_mismatch(self, cin: str, incorporation_date: str) -> None:
        """
        Cross-check the page's incorporation date against the year encoded
        in the CIN. A disagreement means one of the two was misread, so it
        is worth a warning rather than silently trusting either.
        """
        match = CIN_PATTERN.search(cin)
        if not match:
            return

        if incorporation_date[:4] != match.group(1):
            logger.warning(
                f"CIN year {match.group(1)} disagrees with incorporation date "
                f"{incorporation_date} for {cin}"
            )
