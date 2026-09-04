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
        self._playwright = None
        self._browser = None

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
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    def _is_thin_content(self, content: ScrapedContent) -> bool:
        """
        Detect a scrape that's suspiciously empty - typically a JS-only
        single-page app or a client-side geo-redirect gate (e.g.
        prolifics.com), where the static HTML has no real content until
        JavaScript runs. No on-page links AND almost no visible text is a
        strong signal a real homepage wouldn't produce.
        """
        return not content.links and len(content.raw_text.strip()) < 200

    async def _render_with_browser(self, url: str) -> Optional[str]:
        """
        Render a page with a headless browser so its JavaScript actually
        runs, for pages a plain HTTP GET can't get real content from.

        Returns the rendered HTML, or None if rendering isn't available or fails.
        """
        try:
            if self._browser is None:
                from playwright.async_api import async_playwright

                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=True)

            page = await self._browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            try:
                # networkidle is unreliable on real sites - trackers/analytics
                # (GTM, HubSpot, LinkedIn Insight, etc.) keep making requests
                # forever, so it just times out. domcontentloaded + a settle
                # window (which also gives client-side redirects, like
                # prolifics.com's geo-redirect gate, time to land) is more robust.
                await page.goto(url, timeout=settings.scraping_playwright_timeout_ms, wait_until="domcontentloaded")
                try:
                    await page.wait_for_load_state("load", timeout=settings.scraping_playwright_timeout_ms)
                except Exception:
                    pass  # good enough - fall through and grab whatever rendered
                await page.wait_for_timeout(2000)

                # A client-side redirect can still be landing when we ask for
                # content(), which raises rather than blocking - retry briefly.
                for attempt in range(3):
                    try:
                        return await page.content()
                    except Exception:
                        if attempt == 2:
                            raise
                        await page.wait_for_timeout(1500)
            finally:
                await page.close()

        except ImportError:
            logger.warning("Playwright is not installed; skipping headless-browser fallback")
            return None
        except Exception as e:
            logger.warning(f"Headless-browser render failed for {url}: {e}")
            return None

    def _build_content(self, url: str, html: str) -> ScrapedContent:
        """Parse raw HTML into structured ScrapedContent."""
        soup = BeautifulSoup(html, "html.parser")

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

        # Extract emails and phones from ALL visible text on page,
        # not just <p> tags - this catches contact info in
        # divs, spans, footers, sections, list items, etc.
        all_visible_text = self._extract_all_visible_text(soup)
        content.emails = extract_emails(all_visible_text)
        content.phones = extract_phones(all_visible_text)

        # Store truncated raw text
        all_text = " ".join(content.paragraphs)
        content.raw_text = truncate_text(all_text, settings.scraping_max_content_length)

        return content

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

                content = self._build_content(url, response.text)

                if settings.scraping_playwright_fallback and self._is_thin_content(content):
                    logger.info(f"Static scrape too thin for {url}, retrying with headless browser")
                    rendered_html = await self._render_with_browser(url)
                    if rendered_html:
                        rendered_content = self._build_content(url, rendered_html)
                        if not self._is_thin_content(rendered_content):
                            content = rendered_content

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

    def _extract_all_visible_text(self, soup: BeautifulSoup) -> str:
        """
        Extract ALL visible text from the page body (not just <p> tags).
        This captures phones, addresses, and contact info that may be
        in <div>, <span>, <footer>, <a>, <li>, <section>, etc.

        Many modern websites put contact details outside <p> tags,
        so scanning only paragraphs misses them. This method grabs
        everything visible in the body.
        """
        # Remove non-visible elements
        for element in soup(["script", "style", "noscript", "iframe"]):
            element.decompose()

        body = soup.find("body")
        if not body:
            return ""

        text = body.get_text(separator=" ", strip=True)
        text = clean_html_text(text)
        return text

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
