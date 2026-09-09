"""
AI analysis service for processing company information with LLMs.

This module sends extracted content to an LLM and generates
structured JSON output about the company in the exact format
consumed by the Java frontend.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, List

import httpx

from models import (
    CompanyInfo,
    CompanyMetadata,
    CompanyCandidate,
    SearchResult,
    ReviewEvidence,
    ReviewInsights,
    ReviewPoint,
)
from config import settings


logger = logging.getLogger("company_intelligence.ai_analyzer")


class AIAnalyzerService:
    """Service for AI-powered company analysis."""

    def __init__(self):
        """Initialize the AI analyzer service."""
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.timeout = settings.llm_timeout

    async def analyze_company(
        self,
        company_name: str,
        content: str,
        initial_info: CompanyInfo
    ) -> CompanyInfo:
        """
        Analyze company content using LLM.

        The LLM returns a structured JSON that enriches the CompanyInfo
        with AI-generated insights on industry, services, technologies,
        and overview.

        Args:
            company_name: Name of the company
            content: Combined text content from website
            initial_info: Initially extracted company information

        Returns:
            Enhanced CompanyInfo with LLM-generated insights
        """
        if not self.api_key:
            logger.warning("No API key provided, returning initial info without AI analysis")
            return initial_info

        logger.info(f"Analyzing company with AI: {company_name}")

        try:
            prompt = self._build_analysis_prompt(company_name, content, initial_info)
            response = await self._call_llm(prompt)

            if response:
                # Merge AI response with initial info
                enhanced_info = self._merge_analysis(initial_info, response)
                logger.info(f"AI analysis completed successfully for '{company_name}'")
                return enhanced_info
            else:
                logger.warning("AI analysis returned no results, returning initial info")
                return initial_info

        except Exception as e:
            logger.error(f"AI analysis failed for '{company_name}': {e}", exc_info=True)
            return initial_info

    def _build_analysis_prompt(
        self,
        company_name: str,
        content: str,
        initial_info: CompanyInfo
    ) -> str:
        """Build the analysis prompt for the LLM."""
        # Include scraped data as context for the LLM
        scraped_context = ""
        if initial_info.emails:
            scraped_context += f"\nScraped Emails: {', '.join(initial_info.emails)}"
        if initial_info.phones:
            scraped_context += f"\nScraped Phones: {', '.join(initial_info.phones)}"
        if initial_info.address:
            scraped_context += f"\nScraped Address: {initial_info.address}"
        if initial_info.social_links:
            scraped_context += f"\nScraped Social Links: {json.dumps(initial_info.social_links)}"

        return f"""You are a business intelligence analyzer. Analyze the following company website content and return ONLY a valid JSON object. No markdown, no extra text.

Company Name: {company_name}

Website Content (scraped from homepage, about, and contact pages):
{content[:12000]}

{scraped_context}

Return a JSON object with this exact structure:
{{
  "industry": "Most specific industry sector (e.g., 'Information Technology & Services', 'Financial Services', 'Healthcare'). Use 'Not Found' if unclear.",
  "description": "A 5-sentence professional company description based on the content - one sentence each on: what the company does, who it serves, its core services/products, what differentiates it, and its scale or market position (skip any point the content doesn't support rather than padding).",
  "services": ["List", "of", "key", "business", "services", "offered"],
  "technologies": ["List", "of", "technologies", "platforms", "or", "tools", "mentioned"],
  "address": "The company's real postal/office address (street, city, state/region, postal code), if one is genuinely present in the content. Use 'Not Found' if there is none - do NOT use a marketing sentence like '100+ companies trust us' as an address, and do NOT invent one.",
  "overview": "A comprehensive 2-3 paragraph overview covering: what the company does, their market position, key offerings, and any notable information."
}}

Critical Rules:
- Return ONLY valid JSON - no markdown formatting, no code fences, no extra text
- If information is not in the provided content, use "Not Found" - DO NOT hallucinate
- Services and technologies must be arrays (can be empty if nothing found)
- Description should be around 5 sentences - do not pad with filler if the content doesn't support that much detail
- Overview must be substantive (at least 2 paragraphs) using only provided content
- Industry should be as specific as possible based on available context
- The "Scraped Address" above (if present) was extracted heuristically and may be wrong (e.g. a marketing sentence) - verify it against the actual content rather than trusting it, and correct it if the content shows a real address elsewhere or none at all
"""

    async def _call_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Make API call to the LLM."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a business intelligence analyzer. You ALWAYS return only valid JSON objects, no additional text, no markdown formatting."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": self.temperature,
                        "response_format": {"type": "json_object"}
                    }
                )
                response.raise_for_status()

                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # Parse JSON response
                analysis = json.loads(content)
                logger.debug(f"LLM response parsed successfully: {len(content)} chars")
                return analysis

        except httpx.TimeoutException:
            logger.error(f"LLM API call timed out after {self.timeout}s")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API returned HTTP {e.response.status_code}: {e.response.text[:200]}")
            return None
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling LLM: {e}")
            return None
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing LLM response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling LLM: {e}", exc_info=True)
            return None

    def _merge_analysis(
        self,
        initial_info: CompanyInfo,
        analysis: Dict[str, Any]
    ) -> CompanyInfo:
        """Merge AI analysis with initial company info."""
        # Update fields with AI-generated content
        if "industry" in analysis and analysis.get("industry"):
            initial_info.industry = analysis["industry"]
            logger.debug(f"AI set industry: {initial_info.industry}")

        if "description" in analysis and analysis.get("description"):
            initial_info.description = analysis["description"]
            logger.debug(f"AI set description: {initial_info.description[:100]}...")

        if "services" in analysis and analysis.get("services"):
            initial_info.services = analysis["services"]
            logger.debug(f"AI set services ({len(initial_info.services)} items)")

        if "technologies" in analysis and analysis.get("technologies"):
            initial_info.technologies = analysis["technologies"]
            logger.debug(f"AI set technologies ({len(initial_info.technologies)} items)")

        if "address" in analysis and analysis.get("address"):
            # AI overrides the heuristic guess even with "Not Found" - that
            # means it looked at the heuristic's guess and rejected it
            # (e.g. a marketing sentence), which is more reliable than
            # leaving a wrong heuristic address in place.
            initial_info.address = analysis["address"]
            logger.debug(f"AI set address: {initial_info.address}")

        if "overview" in analysis and analysis.get("overview"):
            initial_info.overview = analysis["overview"]
            logger.debug(f"AI set overview: {initial_info.overview[:100]}...")

        return initial_info

    async def classify_company_candidates(
        self,
        company_name: str,
        candidates: List[CompanyCandidate],
        raw_results: List[SearchResult],
    ) -> List[CompanyCandidate]:
        """
        Refine disambiguation candidates with the LLM: fill in country/
        description where the heuristics couldn't, and correctly flag
        results that aren't actually a company profile (e.g. a news
        article or crypto listing reusing the same name).

        Falls back to the heuristic candidates unchanged if no API key is
        configured or the LLM call fails - this step is a refinement, not
        a requirement.

        Args:
            company_name: Name being disambiguated
            candidates: Heuristic candidates, keyed by `website`
            raw_results: The underlying search results for extra context

        Returns:
            Candidates with AI-refined fields, or the original list on failure
        """
        if not self.api_key or not candidates:
            return candidates

        logger.info(f"Classifying {len(candidates)} candidates with AI: {company_name}")

        try:
            prompt = self._build_disambiguation_prompt(company_name, raw_results)
            response = await self._call_llm(prompt)

            if response and isinstance(response.get("candidates"), list):
                return self._merge_candidate_analysis(candidates, response["candidates"])

            logger.warning("AI classification returned no usable candidates, keeping heuristics")
            return candidates

        except Exception as e:
            logger.error(f"AI candidate classification failed for '{company_name}': {e}", exc_info=True)
            return candidates

    def _build_disambiguation_prompt(self, company_name: str, raw_results: List[SearchResult]) -> str:
        """Build the prompt for classifying search results into distinct entities."""
        results_block = "\n".join(
            f"- website: {r.url}\n  title: {r.title}\n  snippet: {r.description[:300]}"
            for r in raw_results
        )

        return f"""You are disambiguating search results for the company name "{company_name}". Some results may belong to a DIFFERENT entity that happens to share the name (e.g. a crypto token, an unrelated business, a news article about a third party). Return ONLY a valid JSON object, no markdown, no extra text.

Search results:
{results_block}

Return a JSON object with this exact structure:
{{
  "candidates": [
    {{
      "website": "the exact website value from the input above",
      "name": "the entity's actual name",
      "country": "country the entity is based in, or null if unknown - do not guess from the TLD alone",
      "description": "one sentence describing what this entity is, or null",
      "type": "null if this is a genuine company profile matching '{company_name}'; otherwise a short label like 'Crypto price page', 'News article', 'Unrelated company' explaining why it is NOT a company profile"
    }}
  ]
}}

Critical Rules:
- Return ONLY valid JSON - no markdown formatting, no code fences, no extra text
- Include one entry per website from the input, matched by the exact `website` value
- Do not hallucinate country or description - use null when the content doesn't support it
- Set "type" only for results that are NOT a legitimate company profile
"""

    def _merge_candidate_analysis(
        self,
        candidates: List[CompanyCandidate],
        analysis: List[Dict[str, Any]],
    ) -> List[CompanyCandidate]:
        """Merge AI-classified fields into the heuristic candidates, matched by website."""
        by_url = {item.get("website", ""): item for item in analysis if isinstance(item, dict)}

        merged = []
        for candidate in candidates:
            # AI results are keyed by the raw result URL; candidates may hold
            # a bare domain (website field), so match on substring containment.
            match = by_url.get(candidate.website)
            if not match:
                match = next(
                    (item for url, item in by_url.items() if candidate.website in url or url in candidate.website),
                    None,
                )

            if not match:
                merged.append(candidate)
                continue

            resolved_type = match.get("type") or candidate.type
            merged.append(CompanyCandidate(
                name=match.get("name") or candidate.name,
                website=candidate.website,
                # A non-company result carries `type` instead of country/description.
                country=None if resolved_type else (match.get("country") or candidate.country),
                description=None if resolved_type else (match.get("description") or candidate.description),
                type=resolved_type,
            ))

        return merged

    async def synthesize_reviews(
        self,
        company_name: str,
        evidence: "ReviewEvidence",
    ) -> "ReviewInsights":
        """
        Distil gathered review snippets into positive and negative points.

        Every returned point must name a `source_domain` that appears in
        the evidence; points naming anything else are dropped in
        `_merge_review_analysis`. This is enforced in code rather than
        trusted from the prompt because an invented review in a
        due-diligence report is far more damaging than a short list - a
        client could onboard a bad vendor on the strength of praise that
        no one ever wrote.

        Args:
            company_name: Company the reviews are about
            evidence: Gathered snippets, ratings and sources

        Returns:
            ReviewInsights - carries the ratings and sources even when no
            LLM is configured or the call fails, so the UI can still show
            the review links it found.
        """
        base = ReviewInsights(
            employer_rating=evidence.employer_rating,
            business_rating=evidence.business_rating,
            sources=evidence.sources,
            confidence=evidence.confidence,
        )

        if not evidence.snippets:
            base.summary = "No public reviews found for this company."
            return base

        if not self.api_key:
            logger.warning("No API key provided, returning review sources without distilled points")
            base.summary = "Review sources found, but AI analysis is unavailable (no API key configured)."
            return base

        logger.info(f"Synthesizing {len(evidence.snippets)} review snippet(s) for: {company_name}")

        try:
            prompt = self._build_review_prompt(company_name, evidence)
            response = await self._call_llm(prompt)

            if not response:
                logger.warning("Review synthesis returned no results, keeping sources only")
                base.summary = "Review sources found, but the AI summary could not be generated."
                return base

            return self._merge_review_analysis(base, evidence, response)

        except Exception as e:
            logger.error(f"Review synthesis failed for '{company_name}': {e}", exc_info=True)
            base.summary = "Review sources found, but the AI summary could not be generated."
            return base

    def _build_review_prompt(self, company_name: str, evidence: "ReviewEvidence") -> str:
        """Build the prompt that distils review snippets into points."""
        max_points = settings.reviews_max_points

        evidence_block = "\n".join(
            f"[{i}] domain: {s.domain} | type: {s.category}"
            f"{f' | rating: {s.rating}/5' if s.rating is not None else ''}\n"
            f"    title: {s.title}\n"
            f"    snippet: {s.snippet[:400]}"
            for i, s in enumerate(evidence.snippets, start=1)
        )

        allowed_domains = sorted({s.domain for s in evidence.snippets})

        return f"""You are a vendor due-diligence analyst. A client is deciding whether to work with "{company_name}". Below are public review-site search snippets about them. Distil these into positive and negative points. Return ONLY a valid JSON object, no markdown, no extra text.

Review evidence:
{evidence_block}

The review sites fall into two kinds, and they answer different questions:
- type "employer" (AmbitionBox, Glassdoor, Indeed): what it is like to work AT the company. Relevant to the client because high attrition, unpaid salaries or management chaos predict delivery risk.
- type "business" / "consumer" (Clutch, G2, Trustpilot, MouthShut): what it is like to work WITH them as a supplier - delivery quality, deadlines, billing disputes.

Return a JSON object with this exact structure:
{{
  "positives": [
    {{
      "point": "One sentence stating a positive, specific and concrete",
      "source_domain": "the exact domain from the evidence above that supports this",
      "category": "short label, e.g. 'delivery quality', 'management', 'work culture', 'pricing'"
    }}
  ],
  "negatives": [
    {{
      "point": "One sentence stating a negative or complaint",
      "source_domain": "the exact domain from the evidence above that supports this",
      "category": "short label"
    }}
  ],
  "summary": "Two sentences: whether the review record supports working with this company, and the single biggest caveat. Say plainly if the evidence is too thin to judge."
}}

Critical Rules:
- Return ONLY valid JSON - no markdown formatting, no code fences, no extra text
- Up to {max_points} positives and up to {max_points} negatives
- DO NOT INVENT POINTS. Every point must be supported by the snippets above. If the evidence only supports 4 positives, return 4 - a short honest list is required, padding is a serious error
- "source_domain" MUST be copied exactly from one of these: {", ".join(allowed_domains)}
- Any point whose source_domain is not in that list will be discarded
- Do not restate the company's own marketing as a review point
- Keep each point to one sentence, specific rather than generic ("pays vendors 60-90 days late" not "some payment issues")
- If the snippets are only ratings with no substance, return few or no points and say so in the summary
"""

    def _merge_review_analysis(
        self,
        base: "ReviewInsights",
        evidence: "ReviewEvidence",
        analysis: Dict[str, Any],
    ) -> "ReviewInsights":
        """
        Validate LLM review points against the gathered evidence.

        A point is kept only if its `source_domain` is one the gatherer
        actually saw. Anything else is a fabrication (or a mangled domain)
        and is dropped with a warning rather than shown to a client.
        """
        allowed_domains = {s.domain for s in evidence.snippets}
        max_points = settings.reviews_max_points

        def clean(raw_points: Any) -> List[ReviewPoint]:
            kept: List[ReviewPoint] = []
            for item in raw_points or []:
                if not isinstance(item, dict):
                    continue

                text = (item.get("point") or "").strip()
                domain = (item.get("source_domain") or "").strip().lower()

                if not text:
                    continue
                if domain not in allowed_domains:
                    logger.warning(
                        f"Dropping unattributable review point (source {domain!r} "
                        f"not in gathered evidence): {text[:80]}"
                    )
                    continue

                kept.append(ReviewPoint(
                    point=text,
                    source_domain=domain,
                    category=(item.get("category") or "general").strip(),
                ))

                if len(kept) >= max_points:
                    break
            return kept

        base.positives = clean(analysis.get("positives"))
        base.negatives = clean(analysis.get("negatives"))

        summary = (analysis.get("summary") or "").strip()
        base.summary = summary or "Not Found"

        # A model that could not attribute anything means the snippets held
        # no real substance, whatever the site count suggested.
        if not base.positives and not base.negatives:
            base.confidence = "low"

        logger.info(
            f"Review synthesis kept {len(base.positives)} positive(s) and "
            f"{len(base.negatives)} negative(s)"
        )
        return base

    async def analyze_without_api(self, initial_info: CompanyInfo) -> CompanyInfo:
        """Return initial info when no API key is available."""
        initial_info.industry = "Not Found"
        initial_info.overview = "AI analysis not available - no API key configured"
        return initial_info
