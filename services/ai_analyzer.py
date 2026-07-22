"""
AI analysis service for processing company information with LLMs.

This module sends extracted content to an LLM and generates
structured JSON output about the company.
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
            prompt = self._build_analysis_prompt(company_name, content)
            response = await self._call_llm(prompt)

            if response:
                # Merge AI response with initial info
                enhanced_info = self._merge_analysis(initial_info, response)
                logger.info("AI analysis completed successfully")
                return enhanced_info
            else:
                logger.warning("AI analysis returned no results, returning initial info")
                return initial_info

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return initial_info

    def _build_analysis_prompt(self, company_name: str, content: str) -> str:
        """Build the analysis prompt for the LLM."""
        return f"""Analyze the following company website content and return ONLY a JSON object.

Company Name: {company_name}

Website Content:
{content}

Return a JSON object with this exact structure (no additional text):
{{
  "industry": "Industry sector or 'Not Found'",
  "description": "Brief company description (2-3 sentences)",
  "services": ["service1", "service2", ...],
  "technologies": ["technology1", "technology2", ...],
  "overview": "Comprehensive company overview (3-4 paragraphs)"
}}

Rules:
- Return ONLY valid JSON, no markdown formatting
- If information is not found in the content, use "Not Found"
- Keep services and technologies as arrays
- Do NOT hallucinate or make up information
- Use only the provided website content
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
                                "content": "You are a business intelligence analyzer. Always return valid JSON only."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": self.temperature,
                        "response_format": {{"type": "json_object"}}
                    }
                )
                response.raise_for_status()

                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # Parse JSON response
                analysis = json.loads(content)
                return analysis

        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling LLM: {e}")
            return None
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing LLM response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling LLM: {e}")
            return None

    def _merge_analysis(
        self,
        initial_info: CompanyInfo,
        analysis: Dict[str, Any]
    ) -> CompanyInfo:
        """Merge AI analysis with initial company info."""
        # Update fields with AI-generated content
        if "industry" in analysis:
            initial_info.industry = analysis["industry"] or "Not Found"

        if "description" in analysis:
            initial_info.description = analysis["description"] or initial_info.description

        if "services" in analysis and analysis["services"]:
            initial_info.services = analysis["services"]

        if "technologies" in analysis and analysis["technologies"]:
            initial_info.technologies = analysis["technologies"]

        if "overview" in analysis:
            initial_info.overview = analysis["overview"] or "Not Found"

        return initial_info

    async def analyze_without_api(self, initial_info: CompanyInfo) -> CompanyInfo:
        """Return initial info when no API key is available."""
        initial_info.industry = "Not Found"
        initial_info.overview = "AI analysis not available - no API key configured"
        return initial_info
