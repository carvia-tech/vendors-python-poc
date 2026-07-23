"""
Company disambiguation service using geo-context and AI-powered URL selection.

This module provides automatic disambiguation of same-name companies by:
1. Geo-context scoring (TLD-based region matching)
2. URL quality heuristics (domain authority, name matching)
3. AI-powered final selection when confidence is low

The system is designed to be fully automatic - no user intervention required.
It picks the best-matching URL and returns it with a confidence score.
"""

import json
import logging
from typing import List, Optional, Dict, Tuple
from urllib.parse import urlparse

import httpx
import tldextract

from config import settings, COUNTRY_TO_REGION

logger = logging.getLogger("company_intelligence.disambiguator")


class DisambiguatorService:
    """
    Service for automatically selecting the best company website URL
    from multiple candidates using geo-context and AI analysis.
    """

    def __init__(self):
        """Initialize the disambiguator service."""
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout

    async def resolve_best_url(
        self,
        company_name: str,
        candidates: List[Dict[str, str]],
        region: Optional[str] = None,
        country: Optional[str] = None,
        api_key_override: Optional[str] = None,
    ) -> Tuple[Optional[str], int, str]:
        """
        Resolve the best URL from a list of candidates using geo-scoring + AI fallback.

        This is the main entry point for disambiguation. It:
        1. Scores all candidates using geo-context and URL heuristics
        2. If top score >= threshold → returns it directly
        3. If top score < threshold AND AI key available → uses LLM to pick best
        4. Falls back to highest-scored candidate

        Args:
            company_name: Name of the company being searched
            candidates: List of dicts with 'url', 'title', 'description' keys
            region: Optional geographic region (e.g., "India", "USA")
            country: Optional ISO country code (e.g., "IN", "US")
            api_key_override: Optional API key override for AI disambiguation

        Returns:
            Tuple of (best_url, confidence_score, method_used)
            - method_used is "geo_score", "ai_selected", or "fallback"
        """
        if not candidates:
            logger.warning(f"No candidates provided for '{company_name}'")
            return None, 0, "fallback"

        # Auto-derive region from country if only country is provided
        resolved_region = self._resolve_region(region, country)
        logger.info(
            f"Resolving best URL for '{company_name}' "
            f"(region={resolved_region}, country={country}, "
            f"candidates={len(candidates)})"
        )

        # Step 1: Score all candidates
        scored = self._score_candidates(company_name, candidates, resolved_region)
        scored.sort(key=lambda x: x[1], reverse=True)

        best_url, best_score = scored[0][0], scored[0][1]

        # Step 2: Check if score meets threshold
        if best_score >= settings.disambiguation_min_confidence:
            logger.info(
                f"Geo-score sufficient for '{company_name}': "
                f"{best_url} (score={best_score})"
            )
            return best_url, best_score, "geo_score"

        # Step 3: Try AI disambiguation if API key is available
        ai_key = api_key_override or self.api_key
        if ai_key and len(candidates) > 1:
            logger.info(
                f"Confidence too low ({best_score} < {settings.disambiguation_min_confidence}), "
                f"invoking AI disambiguation for '{company_name}'"
            )
            ai_result = await self._ai_disambiguate(
                company_name, scored[:settings.disambiguation_max_candidates],
                resolved_region, ai_key
            )
            if ai_result:
                ai_url, ai_confidence = ai_result
                logger.info(
                    f"AI selected '{ai_url}' for '{company_name}' "
                    f"(confidence={ai_confidence})"
                )
                return ai_url, ai_confidence, "ai_selected"

        # Step 4: Fallback to best scored candidate
        logger.info(
            f"Using geo-score fallback for '{company_name}': "
            f"{best_url} (score={best_score})"
        )
        return best_url, best_score, "geo_score"

    def _resolve_region(
        self,
        region: Optional[str],
        country: Optional[str]
    ) -> Optional[str]:
        """Derive region from country code if region not provided."""
        if region:
            return region.strip().lower()
        if country and country.upper() in COUNTRY_TO_REGION:
            return COUNTRY_TO_REGION[country.upper()].lower()
        return None

    def _score_candidates(
        self,
        company_name: str,
        candidates: List[Dict[str, str]],
        region: Optional[str]
    ) -> List[Tuple[Dict[str, str], int]]:
        """
        Score each candidate URL using geo-context and heuristics.

        Scoring system (cumulative, max ~85 before penalties):
        - TLD matches region: +30 (configurable)
        - Company name in domain: +20
        - Company name in URL path: +10
        - Has www prefix: +5
        - Social/excluded domain: -50 (heavy penalty)
        - No 'official' in description: -10
        """
        scored = []
        company_lower = company_name.lower()

        # Extract company name words for partial matching
        company_words = set(company_lower.split())
        region_tlds = set()
        if region:
            for reg_key, tlds in settings.region_tld_map.items():
                if region == reg_key or region in reg_key or reg_key in region:
                    region_tlds.update(tlds)

        for candidate in candidates:
            url = candidate.get("url", "")
            title = candidate.get("title", "")
            description = candidate.get("description", "")
            score = 0

            if not url:
                scored.append((candidate, 0))
                continue

            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path.lower()
            extracted = tldextract.extract(url)
            full_domain = f"{extracted.domain}.{extracted.suffix}".lower()

            # --- Positive Scoring ---

            # TLD matches region (highest weight)
            if region and region_tlds:
                for tld in region_tlds:
                    if full_domain.endswith(tld) or domain.endswith(tld):
                        score += settings.disambiguation_score_tld_match
                        break

            # Company name in domain (e.g., microsoft.com)
            if company_lower in domain or company_lower.replace(" ", "") in domain:
                score += settings.disambiguation_score_company_in_domain
            else:
                # Partial word match in domain
                domain_words = set(domain.replace(".", " ").replace("-", " ").split())
                matching_words = company_words & domain_words
                if matching_words:
                    score += min(
                        len(matching_words) * 5,
                        settings.disambiguation_score_company_in_domain
                    )

            # Company name in URL path
            if company_lower in path:
                score += settings.disambiguation_score_company_in_path

            # Has www (indicates a proper website)
            if domain.startswith("www."):
                score += settings.disambiguation_score_has_www

            # --- Penalties ---

            # Social/excluded domain penalty
            excluded_patterns = [
                "linkedin.com", "facebook.com", "twitter.com", "x.com",
                "instagram.com", "youtube.com", "github.com", "wikipedia.org",
                "crunchbase.com", "glassdoor.com", "zoominfo.com",
                "indeed.com", "bloomberg.com", "forbes.com",
            ]
            if any(p in domain for p in excluded_patterns):
                score += settings.disambiguation_score_social_penalty

            # No 'official' in description suggests it might not be the official site
            desc_lower = (description + " " + title).lower()
            if "official" not in desc_lower:
                score += settings.disambiguation_score_no_official_penalty

            # Normalize score to 0-100 range
            # Raw max positive is ~65, so we scale up
            normalized_score = max(0, min(100, score + 35))

            logger.debug(
                f"Scored {url}: raw={score}, normalized={normalized_score}"
            )
            scored.append((candidate, normalized_score))

        return scored

    async def _ai_disambiguate(
        self,
        company_name: str,
        candidates: List[Tuple[Dict[str, str], int]],
        region: Optional[str],
        api_key: str,
    ) -> Optional[Tuple[str, int]]:
        """
        Use LLM to select the best URL from candidates.

        Args:
            company_name: Company name being searched
            candidates: List of (candidate_dict, score) tuples
            region: Resolved region string
            api_key: OpenAI API key

        Returns:
            Tuple of (best_url, confidence_0_to_100) or None if failed
        """
        try:
            prompt = self._build_disambiguation_prompt(company_name, candidates, region)
            response = await self._call_llm(prompt, api_key)

            if not response:
                return None

            best_url = response.get("selected_url", "")
            confidence = response.get("confidence", 50)

            # Validate the URL is actually in our candidate list
            candidate_urls = {c[0].get("url", "") for c in candidates}
            if best_url not in candidate_urls:
                logger.warning(
                    f"AI selected URL '{best_url}' not in candidates, "
                    f"falling back to best scored"
                )
                return None

            return best_url, confidence

        except Exception as e:
            logger.error(f"AI disambiguation failed: {e}", exc_info=True)
            return None

    def _build_disambiguation_prompt(
        self,
        company_name: str,
        candidates: List[Tuple[Dict[str, str], int]],
        region: Optional[str],
    ) -> str:
        """Build the LLM prompt for URL disambiguation."""
        region_context = f" (operating in {region})" if region else ""

        candidates_text = ""
        for i, (candidate, score) in enumerate(candidates, 1):
            url = candidate.get("url", "N/A")
            title = candidate.get("title", "N/A")
            description = candidate.get("description", "N/A")
            candidates_text += f"""
Candidate {i}:
  URL: {url}
  Title: {title}
  Description: {description[:200]}
  Geo-Score: {score}/100
"""

        return f"""You are a business intelligence URL disambiguation expert. Your task is to select the BEST official company website from a list of candidates.

Company Name: "{company_name}"{region_context}

{candidates_text}

Analyze each candidate and choose the one that is MOST LIKELY the official corporate website for this company. Consider:
1. Does the URL clearly represent the company (e.g., companyname.com)?
2. Is it the global/regional headquarters appropriate for the given region?
3. Is it a legitimate corporate site vs. a news article, social media, or third-party listing?
4. Does the title/description match what you'd expect from an official company site?

Return ONLY a valid JSON object with no additional text:
{{
  "selected_url": "the best URL from the candidates",
  "confidence": <integer 0-100 based on how confident you are>,
  "reasoning": "brief explanation of why this URL was selected"
}}"""

    async def _call_llm(
        self,
        prompt: str,
        api_key: str
    ) -> Optional[Dict]:
        """Make API call to the LLM for disambiguation."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a URL disambiguation expert. You ALWAYS return only valid JSON objects, no additional text, no markdown formatting."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.1,  # Low temperature for consistent results
                        "response_format": {"type": "json_object"}
                    }
                )
                response.raise_for_status()

                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return json.loads(content)

        except httpx.TimeoutException:
            logger.error(f"AI disambiguation timed out after {self.timeout}s")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(
                f"AI disambiguation HTTP {e.response.status_code}: "
                f"{e.response.text[:200]}"
            )
            return None
        except Exception as e:
            logger.error(f"AI disambiguation call failed: {e}", exc_info=True)
            return None

    def score_url_quick(
        self,
        company_name: str,
        url: str,
        region: Optional[str] = None,
    ) -> int:
        """
        Quick synchronous scoring for a single URL (useful for logging/debugging).

        Args:
            company_name: Company name
            url: URL to score
            region: Optional region

        Returns:
            Confidence score 0-100
        """
        candidate = {"url": url, "title": "", "description": ""}
        scored = self._score_candidates(company_name, [candidate], region)
        return scored[0][1] if scored else 0

