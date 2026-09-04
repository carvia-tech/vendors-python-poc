"""
Company Information Intelligence Engine - Streamlit Demo Application
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

import streamlit as st

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from models import CompanyCandidate, CompanyIntelligenceResponse
from api.dependencies import search_companies_pipeline, run_enrichment_pipeline
from utils import setup_logging


logger = setup_logging()

st.set_page_config(page_title="Company Intelligence", page_icon="🏢", layout="wide")


class CompanyIntelligenceApp:
    """Main application class."""

    def run(self):
        st.title("🏢 Company Information Intelligence Engine")
        st.markdown("---")

        # API Key in sidebar
        with st.sidebar:
            api_key = st.text_input("OpenAI API Key (Optional)", type="password")
            if api_key:
                settings.llm_api_key = api_key

        st.session_state.setdefault("candidates", None)
        st.session_state.setdefault("query", "")
        st.session_state.setdefault("result", None)

        # Main interface
        col1, col2 = st.columns([4, 1])
        with col1:
            company_name = st.text_input("Company Name or Website", placeholder="e.g., Microsoft or microsoft.com")
        with col2:
            search_button = st.button("Search", type="primary", use_container_width=True)

        if search_button and company_name:
            st.session_state.result = None
            self.run_search(company_name)

        if st.session_state.result is not None:
            if st.button("🔄 New Search"):
                st.session_state.result = None
                st.session_state.candidates = None
                st.rerun()
            self._display_results(st.session_state.result)
        elif st.session_state.candidates is not None:
            self._display_disambiguation(st.session_state.query, st.session_state.candidates)

    def run_search(self, company_name: str):
        """Search for candidates matching the name, disambiguating if needed."""
        with st.spinner(f"Searching for '{company_name}'..."):
            candidates = asyncio.run(search_companies_pipeline(company_name))

        st.session_state.query = company_name

        # An unambiguous single legitimate match - skip straight to
        # enrichment. Anything else (multiple entries, or the only result
        # being a non-company page like a crypto ticker) surfaces the
        # picker so the user can see what was actually found.
        if len(candidates) == 1 and not candidates[0].type:
            st.session_state.candidates = None
            self.run_analysis(company_name, candidates[0].website)
        else:
            st.session_state.candidates = candidates

    def _display_disambiguation(self, company_name: str, candidates: List[CompanyCandidate]):
        st.markdown("---")

        if not candidates:
            st.warning(f"No results found for '{company_name}'.")
            return

        st.subheader(f'Multiple matches for "{company_name}" — pick one')

        for idx, candidate in enumerate(candidates):
            with st.container(border=True):
                cols = st.columns([4, 1])
                with cols[0]:
                    st.markdown(f"**{candidate.name}**")
                    st.caption(f"🌐 {candidate.website}")
                    if candidate.type:
                        st.caption(f"⚠️ {candidate.type} — not a company profile")
                    else:
                        if candidate.country:
                            st.caption(f"📍 {candidate.country}")
                        if candidate.description:
                            st.caption(candidate.description)
                with cols[1]:
                    if st.button(
                        "Get Details",
                        key=f"select_candidate_{idx}",
                        disabled=bool(candidate.type),
                        use_container_width=True,
                    ):
                        st.session_state.candidates = None
                        self.run_analysis(company_name, candidate.website)
                        st.rerun()

    def run_analysis(self, company_name: str, website: Optional[str] = None):
        progress_bar = st.progress(0)
        status_text = st.empty()

        async def progress_callback(step: int, message: str):
            progress_bar.progress(step / 6)
            status_text.text(message)

        result = asyncio.run(run_enrichment_pipeline(
            company_name=company_name,
            website=website,
            progress_callback=progress_callback,
        ))

        st.session_state.result = result

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
