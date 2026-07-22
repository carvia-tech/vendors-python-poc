"""
Web scraping service for extracting content from company websites.

This module uses async HTTP requests with httpx and BeautifulSoup
to extract structured content from web pages.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any

import httpx
from bs4 import BeautifulSoup

from models import ScrapedContent
from config import settings
from utils import (
    truncate_text,
    clean_html_text,
    extract_emails,
    extract_phones,
    normalize_url,
    is_about_page,
    is_contact_page,
    is_careers_page,
    get_domain_from_url,
)


logger = logging.getLogger("company_intelligence.scraper")


class ScraperService:
    """Service for scraping web pages."""

    def __init__(self):
        """Initialize the scraper service."""
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(
            timeout=settings.scraping_timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()

    async def scrape_page(self, url: str, max_retries: int = 2) -> Optional[ScrapedContent]:
        """
        Scrape a single page and extract structured content.

        Args:
            url: URL to scrape
            max_retries: Maximum number of retry attempts

        Returns:
            ScrapedContent if successful, None otherwise
        """
        logger.info(f"Scraping page: {url}")

        for attempt in range(max_retries + 1):
            try:
                if not self.client:
                    raise RuntimeError("ScraperService not initialized as context manager")

                response = await self.client.get(url)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")

                content = ScrapedContent(
                    url=url,
                    title=self._extract_title(soup),
                    description=self._extract_meta_description(soup),
                    headings=self._extract_headings(soup),
                    paragraphs=self._extract_paragraphs(soup),
                    links=self._extract_links(soup, url),
                    emails=[],
                    phones=[],
                    raw_text=""
                )

                # Extract emails and phones from all text content
                all_text = " ".join(content.paragraphs)
                content.emails = extract_emails(all_text)
                content.phones = extract_phones(all_text)

                # Store truncated raw text
                content.raw_text = truncate_text(all_text, settings.scraping_max_content_length)

                logger.info(f"Successfully scraped: {url}")
                return content

            except httpx.HTTPError as e:
                logger.warning(f"HTTP error on attempt {attempt + 1}: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(1)
                    continue
                else:
                    logger.error(f"Failed to scrape after {max_retries} retries: {url}")
                    return None

            except Exception as e:
                logger.error(f"Unexpected error scraping {url}: {e}")
                return None

    async def scrape_multiple_pages(
        self,
        urls: List[str]
    ) -> Dict[str, Optional[ScrapedContent]]:
        """
        Scrape multiple pages concurrently.

        Args:
            urls: List of URLs to scrape

        Returns:
            Dictionary mapping URLs to scraped content
        """
        logger.info(f"Scraping {len(urls)} pages concurrently")

        tasks = [self.scrape_page(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Map results back to URLs
        content_map = {}
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                logger.error(f"Error scraping {url}: {result}")
                content_map[url] = None
            else:
                content_map[url] = result

        return content_map

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        if title_tag := soup.find("title"):
            return clean_html_text(title_tag.get_text())
        return ""

    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        """Extract meta description."""
        if meta := soup.find("meta", attrs={"name": "description"}):
            return meta.get("content", "")
        return ""

    def _extract_headings(self, soup: BeautifulSoup) -> List[str]:
        """Extract all heading text."""
        headings = []
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            text = clean_html_text(tag.get_text())
            if text:
                headings.append(text)
        return headings

    def _extract_paragraphs(self, soup: BeautifulSoup) -> List[str]:
        """Extract all paragraph text."""
        # Remove script and style elements
        for element in soup(["script", "style", "noscript", "iframe"]):
            element.decompose()

        paragraphs = []
        for p in soup.find_all("p"):
            text = clean_html_text(p.get_text())
            if len(text) > 20:  # Filter out very short paragraphs
                paragraphs.append(text)

        return paragraphs

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract all links including social media links."""
        from urllib.parse import urljoin

        base_domain = get_domain_from_url(base_url)
        links = []

        # Social media domains to include even if external
        social_domains = {
            "linkedin.com", "twitter.com", "x.com", "facebook.com",
            "instagram.com", "youtube.com", "github.com"
        }

        for a in soup.find_all("a", href=True):
            href = a.get("href")
            absolute = urljoin(base_url, href)

            link_domain = get_domain_from_url(absolute)

            # Include internal links OR known social media links
            if link_domain == base_domain or any(social in link_domain for social in social_domains):
                links.append(normalize_url(absolute))

        # Remove duplicates while preserving order
        seen = set()
        return [x for x in links if not (x in seen or seen.add(x))]

    async def find_special_pages(self, homepage_url: str) -> Dict[str, str]:
        """
        Find special pages like About, Contact, and Careers.

        Args:
            homepage_url: URL of the homepage

        Returns:
            Dictionary with page types as keys and URLs as values
        """
        logger.info(f"Finding special pages for: {homepage_url}")

        # First scrape homepage to find links
        homepage_content = await self.scrape_page(homepage_url)
        if not homepage_content:
            return {"about": "Not Found", "contact": "Not Found", "careers": "Not Found"}

        soup = None
        try:
            response = await self.client.get(homepage_url)
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            logger.error(f"Error fetching homepage for finding links: {e}")
            return {"about": "Not Found", "contact": "Not Found", "careers": "Not Found"}

        result = {
            "about": "Not Found",
            "contact": "Not Found",
            "careers": "Not Found"
        }

        # Check existing links first
        for link in homepage_content.links:
            if result["about"] == "Not Found" and is_about_page(link):
                result["about"] = link
            if result["contact"] == "Not Found" and is_contact_page(link):
                result["contact"] = link
            if result["careers"] == "Not Found" and is_careers_page(link):
                result["careers"] = link

        logger.info(f"Found special pages: {result}")
        return result
