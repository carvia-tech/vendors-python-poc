"""
Company Information Intelligence Engine - Streamlit Demo Application
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from models import CompanyInfo, CompanyMetadata, CompanyIntelligenceResponse
from services.search import SearchService
from services.scraper import ScraperService
from services.extractor import ExtractorService
from services.ai_analyzer import AIAnalyzerService
from utils import setup_logging


logger = setup_logging()

st.set_page_config(page_title="Company Intelligence", page_icon="🏢", layout="wide")


class CompanyIntelligenceApp:
    """Main application class."""

    def __init__(self):
        self.search_service = SearchService()
        self.extractor_service = ExtractorService()
        self.ai_service = AIAnalyzerService()

    def run(self):
        st.title("🏢 Company Information Intelligence Engine")
        st.markdown("---")

        # API Key in sidebar
        with st.sidebar:
            api_key = st.text_input("OpenAI API Key (Optional)", type="password")
            if api_key:
                settings.llm_api_key = api_key

        # Main interface
        col1, col2 = st.columns([4, 1])
        with col1:
            company_name = st.text_input("Company Name", placeholder="e.g., Microsoft")
        with col2:
            search_button = st.button("Search", type="primary", use_container_width=True)

        if search_button and company_name:
            self.run_analysis(company_name)

    def run_analysis(self, company_name: str):
        progress_bar = st.progress(0)
        status_text = st.empty()

        result = asyncio.run(self._analyze_company(company_name, progress_bar, status_text))

        if result:
            self._display_results(result)

    async def _analyze_company(self, company_name: str, progress_bar, status_text):
        def update_progress(step: int, message: str):
            progress_bar.progress(step / 6)
            status_text.text(message)
            logger.info(message)

        try:
            update_progress(1, "Searching web...")
            official_url = await self.search_service.search_official_website(company_name)

            if not official_url:
                update_progress(6, "No official website found")
                return self._create_failed_response(company_name, "No official website found")

            update_progress(2, f"Found: {official_url}")

            async with ScraperService() as scraper:
                update_progress(3, "Scraping homepage...")
                homepage_content = await scraper.scrape_page(official_url)
                special_pages = await scraper.find_special_pages(official_url)

                update_progress(4, "Scraping additional pages...")
                pages_to_scrape = []
                about_url = special_pages.get("about")
                contact_url = special_pages.get("contact")

                if about_url and about_url != "Not Found":
                    pages_to_scrape.append(about_url)
                if contact_url and contact_url != "Not Found":
                    pages_to_scrape.append(contact_url)

                scraped_pages = await scraper.scrape_multiple_pages(pages_to_scrape)
                about_content = scraped_pages.get(about_url) if about_url in scraped_pages else None
                contact_content = scraped_pages.get(contact_url) if contact_url in scraped_pages else None

                update_progress(5, "Extracting information...")
                company_info = self.extractor_service.extract_company_info(
                    homepage_content=homepage_content,
                    about_content=about_content,
                    contact_content=contact_content,
                    careers_content=None,
                    special_pages=special_pages
                )

                if settings.llm_api_key:
                    combined_content = self.extractor_service.combine_content_for_ai(
                        homepage_content, about_content, contact_content
                    )
                    company_info = await self.ai_service.analyze_company(
                        company_name, combined_content, company_info
                    )
                else:
                    company_info.industry = "Not Found"
                    company_info.overview = "Not Found"

                update_progress(6, "Complete!")

                metadata = CompanyMetadata(
                    source="Official Website",
                    confidence=100,
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    status="Success"
                )

                return CompanyIntelligenceResponse(company=company_info, metadata=metadata)

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            update_progress(6, f"Failed: {str(e)}")
            return self._create_failed_response(company_name, str(e))

    def _create_failed_response(self, company_name: str, error: str) -> CompanyIntelligenceResponse:
        company_info = CompanyInfo(
            name=company_name,
            industry="Not Found",
            description="Analysis failed",
            website="",
            overview=f"Analysis failed: {error}"
        )
        metadata = CompanyMetadata(
            source="Analysis Failed",
            confidence=0,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            status="Failed"
        )
        return CompanyIntelligenceResponse(company=company_info, metadata=metadata)

    def _display_results(self, result: CompanyIntelligenceResponse):
        st.markdown("---")

        company = result.company

        # Basic info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Company", company.name)
            if company.website:
                st.caption(f"🌐 {company.website}")
        with col2:
            st.metric("Industry", company.industry)
        with col3:
            st.metric("Status", result.metadata.status)

        # Description
        if company.description:
            st.subheader("Description")
            st.write(company.description)

        # Services & Technologies
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Services")
            if company.services:
                for service in company.services:
                    st.caption(f"• {service}")
            else:
                st.caption("None found")
        with col2:
            st.subheader("Technologies")
            if company.technologies:
                for tech in company.technologies:
                    st.caption(f"• {tech}")
            else:
                st.caption("None found")

        # Contact
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Contact")
            if company.emails:
                for email in company.emails:
                    st.caption(f"📧 {email}")
            if company.phones:
                for phone in company.phones:
                    st.caption(f"📱 {phone}")
        with col2:
            st.subheader("Social")
            if company.social_links:
                for platform, link in company.social_links.items():
                    st.caption(f"🔗 [{platform}]({link})")

        # JSON Output
        st.markdown("---")
        st.subheader("JSON Output")
        response_dict = {
            "company": company.model_dump(),
            "metadata": result.metadata.model_dump()
        }
        st.json(response_dict)


def main():
    app = CompanyIntelligenceApp()
    app.run()


if __name__ == "__main__":
    main()
