"""
Information extraction service for aggregating scraped content.

This module combines content from multiple pages and extracts
structured information about the company.
"""

import logging
import re
from typing import List, Dict, Optional, Any

from models import ScrapedContent, CompanyInfo
from utils import clean_html_text, get_domain_from_url, truncate_text


logger = logging.getLogger("company_intelligence.extractor")


class ExtractorService:
    """Service for extracting structured information from scraped content."""

    def __init__(self):
        """Initialize the extractor service."""

    def extract_company_info(
        self,
        homepage_content: Optional[ScrapedContent],
        about_content: Optional[ScrapedContent],
        contact_content: Optional[ScrapedContent],
        careers_content: Optional[ScrapedContent],
        special_pages: Dict[str, str]
    ) -> CompanyInfo:
        """
        Extract structured company information from scraped content.

        Args:
            homepage_content: Scraped homepage content
            about_content: Scraped about page content
            contact_content: Scraped contact page content
            careers_content: Scraped careers page content
            special_pages: Dictionary of special page URLs

        Returns:
            CompanyInfo with extracted data
        """
        logger.info("Extracting company information from scraped content")

        company_info = CompanyInfo()

        # Extract basic information from homepage
        if homepage_content:
            company_info.name = self._extract_company_name(homepage_content)
            company_info.description = self._build_description(homepage_content)
            company_info.website = homepage_content.url

        # Combine all content for analysis
        all_content = []
        if homepage_content:
            all_content.extend(homepage_content.paragraphs)
        if about_content:
            all_content.extend(about_content.paragraphs)
        if contact_content:
            all_content.extend(contact_content.paragraphs)

        # Extract emails and phones from all pages
        company_info.emails = self._collect_emails(
            homepage_content, about_content, contact_content
        )
        company_info.phones = self._collect_phones(
            homepage_content, about_content, contact_content
        )

        # Extract address from contact page
        if contact_content:
            company_info.address = self._extract_address(contact_content)

        # Set special page URLs
        company_info.about_page = special_pages.get("about", "Not Found")
        company_info.contact_page = special_pages.get("contact", "Not Found")
        company_info.careers_page = special_pages.get("careers", "Not Found")

        # Extract social links
        if homepage_content:
            company_info.social_links = self._extract_social_links(homepage_content)

        # Basic services/technologies extraction (fallback without AI)
        company_info.services = self._extract_basic_services(all_content)
        company_info.technologies = self._extract_basic_technologies(all_content)

        # Combine all text for overview with filtering
        all_text = "\n".join(all_content[:100])  # Limit to first 100 paragraphs
        company_info.overview = self._filter_overview_text(all_text[:5000])

        logger.info("Company information extracted successfully")
        return company_info

    def _extract_company_name(self, content: ScrapedContent) -> str:
        """Extract company name from title."""
        title = content.title
        if title:
            for suffix in [
                " - Home", " | Home", " - Official Site", " | Official Site",
                " | ", " - ", " – ", " — ",
                " Consulting", " IT Services", " Digital Transformation",
                " | Consulting", " | IT Services", " | Digital"
            ]:
                if suffix in title:
                    title = title.split(suffix)[0]
                    break
            return title.strip()
        return "Unknown"

    _BOILERPLATE_PATTERNS = ("cookie", "privacy policy", "terms of service", "all rights reserved", "copyright")

    def _build_description(self, content: ScrapedContent) -> str:
        """
        Build a ~5-sentence description without AI.

        The meta description alone is usually just one line - too thin on
        its own - so it's used as the opening sentence, then topped up
        with real homepage paragraphs (skipping cookie/legal boilerplate)
        until there's enough substance.
        """
        parts = []
        if content.description:
            parts.append(content.description.strip())

        for paragraph in content.paragraphs:
            text = paragraph.strip()
            if len(text) < 30 or text in parts:
                continue
            if any(pattern in text.lower() for pattern in self._BOILERPLATE_PATTERNS):
                continue
            parts.append(text)
            if sum(p.count(".") + 1 for p in parts) >= 5:
                break

        if parts:
            return truncate_text(" ".join(parts), 900)
        return content.title or ""

    def _collect_emails(
        self,
        *contents: Optional[ScrapedContent]
    ) -> List[str]:
        """Collect unique emails from all content."""
        emails = set()
        for content in contents:
            if content:
                emails.update(content.emails)
        return sorted(list(emails))

    def _collect_phones(
        self,
        *contents: Optional[ScrapedContent]
    ) -> List[str]:
        """Collect unique phone numbers from all content."""
        phones = set()
        for content in contents:
            if content:
                phones.update(content.phones)
        return sorted(list(phones))

    def _score_address_line(self, line: str) -> int:
        """
        Score how much a line of text looks like a real postal address.

        Word-boundary matching only - a naive substring check previously
        let "ave" (for "Avenue") match inside ordinary words like "have",
        which was enough for a marketing sentence ("100+ companies have
        trusted...") to get picked as an address. A marketing/trust phrase
        is disqualified outright regardless of any keyword coincidence.
        """
        if self._MARKETING_PHRASE_RE.search(line):
            return -100

        score = 0
        if self._POSTAL_CODE_RE.search(line):
            score += 4

        # A leading number ("5G enables...", "24/7 support") or a keyword
        # ("data center", "our office culture") is individually too weak a
        # signal - either false-positives constantly on its own. Require
        # both together (a real street-number-plus-keyword pattern, e.g.
        # "123 Main Street" or "9th Floor") before they count for much.
        has_leading_number = bool(self._LEADING_NUMBER_RE.match(line))
        has_keyword = bool(self._ADDRESS_KEYWORDS_RE.search(line))
        if has_leading_number and has_keyword:
            score += 3
        elif has_keyword:
            score += 1

        if self._COUNTRY_STATE_RE.search(line):
            score += 1
        if line.count(",") >= 1:
            score += 1
        return score

    _POSTAL_CODE_RE = re.compile(r"\b\d{5}(-\d{4})?\b|\b\d{6}\b")
    # Requires whitespace after the number (with an optional ordinal suffix,
    # "9th") so it can't match a number glued to letters like "5G" or "24/7".
    _LEADING_NUMBER_RE = re.compile(r"^\s*\d{1,6}(st|nd|rd|th)?\s+\S")
    _ADDRESS_KEYWORDS_RE = re.compile(
        # Deliberately excludes generic words that collide with ordinary
        # prose - "center" (data center), "place"/"way"/"court"/"square"
        # (figures of speech), standalone "dr" (Doctor) - each previously
        # produced a false-positive "address" out of marketing copy.
        r"\b(street|st|road|rd|avenue|ave|boulevard|blvd|lane|ln|drive|"
        r"plaza|suite|ste|floor|fl|building|tower|block|plot|sector|phase|colony|"
        r"nagar|layout|highway|hwy|office|pincode|pin)\b",
        re.IGNORECASE,
    )
    _COUNTRY_STATE_RE = re.compile(
        r"\b(india|usa|u\.s\.a?\.?|united states|uk|united kingdom|canada|"
        r"australia|singapore|germany|bangalore|bengaluru|mumbai|delhi|"
        r"noida|gurgaon|pune|hyderabad|chennai|kolkata)\b",
        re.IGNORECASE,
    )
    _MARKETING_PHRASE_RE = re.compile(
        r"\b\d+\+?\s*(companies|clients|customers|users|businesses|employees|countries|projects)\b"
        r"|\b(trusted|partnered with|serving|founded in|established in|since \d{4})\b",
        re.IGNORECASE,
    )

    def _extract_address(self, content: ScrapedContent) -> str:
        """
        Extract address from contact page content.

        Scores candidate lines instead of returning the first keyword
        match, so the best-looking address wins rather than whichever
        paragraph happens to appear first.
        """
        # Phase 1: whole paragraphs, which usually hold a complete address intact.
        best_text, best_score = None, 2  # require > 2: a single weak signal isn't enough
        for paragraph in content.paragraphs:
            text = paragraph.strip()
            if not (10 < len(text) < 200):
                continue
            score = self._score_address_line(text)
            if score > best_score:
                best_text, best_score = text, score

        if best_text:
            return best_text

        # Phase 2: addresses in divs/footers/etc aren't captured as <p> tags -
        # fall back to raw text, split into fragments and recombine the
        # ones that look address-like, in their original document order.
        full_text = content.raw_text or " ".join(content.paragraphs)
        fragments = [f.strip() for f in re.split(r"[,\n;]", full_text) if len(f.strip()) > 3]

        kept = []
        for fragment in fragments:
            if self._score_address_line(fragment) >= 3:
                kept.append(fragment)
            if len(kept) >= 4:
                break

        if kept:
            return ", ".join(kept)
        return "Not Found"

    def _extract_social_links(self, content: ScrapedContent) -> Dict[str, str]:
        """Extract social media links from content."""
        social_links = {}

        social_patterns = {
            "linkedin": "linkedin.com/company",
            "twitter": "twitter.com",
            "facebook": "facebook.com",
            "instagram": "instagram.com",
            "youtube": "youtube.com",
            "github": "github.com"
        }

        for link in content.links:
            for platform, pattern in social_patterns.items():
                if pattern in link.lower() and platform not in social_links:
                    social_links[platform] = link

        return social_links

    def _extract_basic_services(self, content: List[str]) -> List[str]:
        """Extract basic services from content using keyword matching."""
        service_keywords = [
            "cloud", "analytics", "consulting", "development", "design",
            "engineering", "infrastructure", "security", "support",
            "integration", "transformation", "digital", "automation",
            "testing", "maintenance", "outsourcing", "advisory"
        ]

        found_services = set()
        all_text_lower = " ".join(content).lower()

        for keyword in service_keywords:
            if keyword in all_text_lower:
                for paragraph in content:
                    if keyword in paragraph.lower():
                        words = paragraph.split()
                        for i, word in enumerate(words):
                            if keyword in word.lower() and len(word) > 3:
                                start = max(0, i - 1)
                                end = min(len(words), i + 2)
                                service = " ".join(words[start:end])
                                found_services.add(service.capitalize())
                                break
                        if len(found_services) >= 5:
                            break
                if len(found_services) >= 5:
                    break

        return sorted(list(found_services))[:5]

    def _extract_basic_technologies(self, content: List[str]) -> List[str]:
        """Extract basic technologies from content."""
        tech_keywords = [
            "python", "java", "javascript", "react", "angular", "vue",
            "node.js", "aws", "azure", "gcp", "kubernetes", "docker",
            "tensorflow", "pytorch", "sap", "salesforce", "mongodb",
            "postgresql", "mysql", "redis", "graphql", "rest api"
        ]

        found_tech = set()
        all_text_lower = " ".join(content).lower()

        for tech in tech_keywords:
            if tech in all_text_lower:
                found_tech.add(tech.capitalize())

        return sorted(list(found_tech))[:5]

    def _filter_overview_text(self, text: str) -> str:
        """Filter overview text to remove unwanted content."""
        unwanted_patterns = [
            "Special characters are not allowed",
            "Maximum length:",
            "Content is generated with AI assistance",
            "All rights reserved",
            "Privacy Policy",
            "Terms of Service",
            "Cookie Policy",
            "Copyright ©",
            "Booth ",
            "Summit",
            "Conference",
        ]

        lines = text.split("\n")
        filtered_lines = []

        for line in lines:
            if not any(pattern.lower() in line.lower() for pattern in unwanted_patterns):
                if len(line.strip()) > 15:
                    filtered_lines.append(line.strip())

        result = " ".join(filtered_lines)
        return result[:3000] if result else "Not Found"

    def combine_content_for_ai(
        self,
        homepage_content: Optional[ScrapedContent],
        about_content: Optional[ScrapedContent],
        contact_content: Optional[ScrapedContent]
    ) -> str:
        """
        Combine content from multiple pages for AI analysis.

        Args:
            homepage_content: Homepage scraped content
            about_content: About page scraped content
            contact_content: Contact page scraped content

        Returns:
            Combined text content
        """
        sections = []

        unwanted_patterns = [
            "Special characters are not allowed",
            "Maximum length:",
            "Content is generated with AI assistance",
            "Copyright",
            "All rights reserved",
            "Privacy Policy",
            "Terms of Service",
            "Cookie Policy",
        ]

        def filter_paragraphs(paragraphs: List[str]) -> List[str]:
            filtered = []
            for p in paragraphs:
                if not any(pattern.lower() in p.lower() for pattern in unwanted_patterns):
                    filtered.append(p)
            return filtered

        if homepage_content:
            sections.append(f"=== HOMEPAGE ===\nTitle: {homepage_content.title}\n")
            sections.extend(filter_paragraphs(homepage_content.paragraphs[:20]))

        if about_content:
            sections.append(f"\n=== ABOUT PAGE ===\n")
            sections.extend(filter_paragraphs(about_content.paragraphs[:30]))

        if contact_content:
            sections.append(f"\n=== CONTACT PAGE ===\n")
            sections.extend(filter_paragraphs(contact_content.paragraphs[:10]))

        combined = "\n".join(sections)
        return combined[:15000]  # Limit for AI prompt
