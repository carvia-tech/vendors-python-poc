"""
Utility functions for the Company Intelligence Engine.

This module contains helper functions for logging, URL handling,
text processing, and other common operations.
"""

import logging
import re
from urllib.parse import urlparse, urljoin, urlunparse
from typing import Optional, List
from bs4 import BeautifulSoup
import tldextract


def setup_logging(name: str = "company_intelligence") -> logging.Logger:
    """
    Configure and return a logger instance.

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(logging.INFO)
    return logger


def is_valid_url(url: str) -> bool:
    """
    Check if a URL is valid and has a proper scheme.

    Args:
        url: URL string to validate

    Returns:
        True if URL is valid, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def normalize_url(url: str) -> str:
    """
    Normalize URL by removing trailing slashes and fragments.

    Args:
        url: URL to normalize

    Returns:
        Normalized URL
    """
    parsed = urlparse(url)
    # Remove fragment and trailing slashes from path
    path = parsed.path.rstrip("/")
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        path,
        parsed.params,
        parsed.query,
        ""  # Remove fragment
    ))


def is_excluded_domain(url: str, excluded_domains: List[str]) -> bool:
    """
    Check if URL belongs to an excluded domain.

    Args:
        url: URL to check
        excluded_domains: List of excluded domain patterns

    Returns:
        True if domain is excluded, False otherwise
    """
    try:
        extracted = tldextract.extract(url)
        domain = f"{extracted.domain}.{extracted.suffix}".lower()

        for excluded in excluded_domains:
            if excluded.lower() in domain:
                return True
        return False
    except Exception:
        return False


def extract_emails(text: str) -> List[str]:
    """
    Extract email addresses from text.

    Args:
        text: Text to search for emails

    Returns:
        List of found email addresses
    """
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    emails = re.findall(email_pattern, text, re.IGNORECASE)
    # Remove duplicates while preserving order
    seen = set()
    return [e for e in emails if not (e in seen or seen.add(e))]


def extract_phones(text: str) -> List[str]:
    """
    Extract phone numbers from text.

    Args:
        text: Text to search for phone numbers

    Returns:
        List of found phone numbers
    """
    # Match various phone number formats
    patterns = [
        r"\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",  # International
        r"\+?\d{1,3}[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}",  # Without parentheses
        r"\d{3}[-.\s]?\d{3}[-.\s]?\d{4}",  # Simple US format
    ]

    phones = []
    for pattern in patterns:
        phones.extend(re.findall(pattern, text))

    # Clean and deduplicate
    cleaned = []
    seen = set()
    for phone in phones:
        # Basic cleanup
        phone = phone.strip()
        if phone and phone not in seen:
            seen.add(phone)
            cleaned.append(phone)

    return cleaned


def truncate_text(text: str, max_length: int = 50000) -> str:
    """
    Truncate text to maximum length while preserving word boundaries.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    # Truncate at word boundary
    truncated = text[:max_length]
    last_space = truncated.rfind(" ")
    if last_space > max_length - 100:
        truncated = truncated[:last_space]

    return truncated + "..."


def clean_html_text(text: str) -> str:
    """
    Clean HTML text by removing extra whitespace.

    Args:
        text: Text to clean

    Returns:
        Cleaned text
    """
    # Replace multiple whitespaces with single space
    text = re.sub(r"\s+", " ", text)
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split("\n")]
    # Filter out empty lines
    lines = [line for line in lines if line]
    return " ".join(lines)


def get_domain_from_url(url: str) -> str:
    """
    Extract domain from URL.

    Args:
        url: URL to extract domain from

    Returns:
        Domain string
    """
    try:
        extracted = tldextract.extract(url)
        return f"{extracted.domain}.{extracted.suffix}".lower()
    except Exception:
        return ""


def is_about_page(url: str) -> bool:
    """
    Check if URL appears to be an about page.

    Args:
        url: URL to check

    Returns:
        True if likely an about page
    """
    about_keywords = ["about", "about-us", "who-we-are", "our-story", "company"]
    path = urlparse(url).path.lower()
    return any(keyword in path for keyword in about_keywords)


def is_contact_page(url: str) -> bool:
    """
    Check if URL appears to be a contact page.

    Args:
        url: URL to check

    Returns:
        True if likely a contact page
    """
    contact_keywords = ["contact", "contact-us", "get-in-touch", "reach-us"]
    path = urlparse(url).path.lower()
    return any(keyword in path for keyword in contact_keywords)


def is_careers_page(url: str) -> bool:
    """
    Check if URL appears to be a careers page.

    Args:
        url: URL to check

    Returns:
        True if likely a careers page
    """
    careers_keywords = ["career", "careers", "jobs", "join-us", "work-with-us", "opportunities"]
    path = urlparse(url).path.lower()
    return any(keyword in path for keyword in careers_keywords)


_TLD_COUNTRY_MAP = {
    "in": "India", "us": "USA", "uk": "United Kingdom", "co.uk": "United Kingdom",
    "ca": "Canada", "au": "Australia", "de": "Germany", "fr": "France",
    "sg": "Singapore", "jp": "Japan", "cn": "China", "nl": "Netherlands",
    "ch": "Switzerland", "ie": "Ireland", "es": "Spain", "it": "Italy",
    "br": "Brazil", "mx": "Mexico", "ae": "UAE", "za": "South Africa",
    "nz": "New Zealand", "se": "Sweden", "no": "Norway", "dk": "Denmark",
    "kr": "South Korea", "hk": "Hong Kong", "il": "Israel", "ru": "Russia",
}

# Generic TLDs give no reliable signal about country (a .com/.io site can be
# registered anywhere), so only unambiguous country-code TLDs are mapped.
def guess_country_from_domain(domain: str) -> Optional[str]:
    """
    Best-effort country guess from a domain's TLD. Returns None for generic
    TLDs (.com, .org, .io, ...) rather than guessing - that's left to AI
    classification when an LLM key is configured.
    """
    try:
        extracted = tldextract.extract(domain)
        suffix = extracted.suffix.lower()
    except Exception:
        return None
    return _TLD_COUNTRY_MAP.get(suffix)


_CRYPTO_DOMAIN_HINTS = [
    "mexc", "binance", "coinbase", "kucoin", "coingecko", "coinmarketcap",
    "okx", "bybit", "kraken", "gate.io", "huobi", "bitfinex",
]
_CRYPTO_PATH_HINTS = ["/price/", "/token/", "/currencies/", "/coin/"]
_NEWS_DOMAIN_HINTS = [
    "prnewswire", "businesswire", "techcrunch", "reuters", "finance.yahoo",
    "marketwatch", "seekingalpha", "benzinga", "globenewswire",
]
_MARKETPLACE_DOMAIN_HINTS = ["amazon.", "ebay.", "alibaba.", "etsy.", "flipkart."]


def classify_non_company_domain(domain: str, url: str) -> Optional[str]:
    """
    Detect results that reuse a company's name but aren't a company profile
    (a crypto ticker page, a news article, a marketplace listing, ...).

    Returns a human-readable type label, or None if the result looks like a
    legitimate company website.
    """
    domain_lower = domain.lower()
    url_lower = url.lower()

    if any(h in domain_lower for h in _CRYPTO_DOMAIN_HINTS) or any(h in url_lower for h in _CRYPTO_PATH_HINTS):
        return "Crypto price page"
    if any(h in domain_lower for h in _NEWS_DOMAIN_HINTS):
        return "News article"
    if any(h in domain_lower for h in _MARKETPLACE_DOMAIN_HINTS):
        return "Marketplace listing"
    return None


_BARE_DOMAIN_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+(/\S*)?$",
    re.IGNORECASE,
)


def looks_like_url(text: str) -> bool:
    """
    True if the input looks like a URL/domain (e.g. "marvell.com",
    "https://marvell.com") rather than a free-text company name.
    Lets a single search field accept either.
    """
    text = text.strip()
    if not text or " " in text:
        return False
    if text.lower().startswith(("http://", "https://")):
        return True
    return bool(_BARE_DOMAIN_RE.match(text))


def ensure_scheme(url: str) -> str:
    """Prepend https:// to a bare domain/URL that has no scheme."""
    if "://" not in url:
        return f"https://{url}"
    return url


def strip_scheme(url: str) -> str:
    """Remove the scheme (and any trailing slash) from a URL for display."""
    return url.split("://", 1)[-1].rstrip("/")


def find_link_by_keywords(soup: BeautifulSoup, keywords: List[str], base_url: str) -> Optional[str]:
    """
    Find a link containing specific keywords.

    Args:
        soup: BeautifulSoup object
        keywords: List of keywords to search for
        base_url: Base URL for resolving relative links

    Returns:
        Absolute URL if found, None otherwise
    """
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        text = link.get_text().lower()

        for keyword in keywords:
            if keyword.lower() in href.lower() or keyword.lower() in text:
                # Convert to absolute URL
                absolute_url = urljoin(base_url, href)
                if is_valid_url(absolute_url):
                    return absolute_url

    return None
