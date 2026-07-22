"""
AI analysis service for processing company information with LLMs.

This module sends extracted content to an LLM and generates
structured JSON output about the company in the exact format
consumed by the Java frontend.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any

import httpx

from models import CompanyInfo, CompanyMetadata
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
  "description": "A 2-3 sentence professional company description based on the content.",
  "services": ["List", "of", "key", "business", "services", "offered"],
  "technologies": ["List", "of", "technologies", "platforms", "or", "tools", "mentioned"],
  "overview": "A comprehensive 2-3 paragraph overview covering: what the company does, their market position, key offerings, and any notable information."
}}

Critical Rules:
- Return ONLY valid JSON - no markdown formatting, no code fences, no extra text
- If information is not in the provided content, use "Not Found" - DO NOT hallucinate
- Services and technologies must be arrays (can be empty if nothing found)
- Overview must be substantive (at least 2 paragraphs) using only provided content
- Industry should be as specific as possible based on available context
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

        if "overview" in analysis and analysis.get("overview"):
            initial_info.overview = analysis["overview"]
            logger.debug(f"AI set overview: {initial_info.overview[:100]}...")

        return initial_info

    async def analyze_without_api(self, initial_info: CompanyInfo) -> CompanyInfo:
        """Return initial info when no API key is available."""
        initial_info.industry = "Not Found"
        initial_info.overview = "AI analysis not available - no API key configured"
        return initial_info
