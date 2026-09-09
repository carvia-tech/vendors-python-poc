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

        # Kept in step with run_enrichment_pipeline's step count; clamped so
        # an extra pipeline step can never push the bar past 100%.
        total_steps = 8

        async def progress_callback(step: int, message: str):
            progress_bar.progress(min(step / total_steps, 1.0))
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

        # Header stays outside the tabs so the company being looked at is
        # always visible, whichever tab is open.
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Company", company.name)
            if company.website:
                st.caption(f"\U0001f310 {company.website}")
        with col2:
            st.metric("Industry", company.industry)
        with col3:
            st.metric("Status", result.metadata.status)

        overview_tab, registry_tab, reviews_tab, json_tab = st.tabs([
            "\U0001f4cb Overview",
            "\U0001f3db\ufe0f Registry",
            "\u2b50 Reviews",
            "\U0001f9fe JSON",
        ])

        with overview_tab:
            self._display_overview(company)
        with registry_tab:
            self._display_registry(company)
        with reviews_tab:
            self._display_reviews(company.reviews)
        with json_tab:
            st.json({
                "company": company.model_dump(),
                "metadata": result.metadata.model_dump(),
            })

    def _display_overview(self, company):
        """Website-derived profile: description, services, contact, social."""
        if company.description:
            st.subheader("Description")
            st.write(company.description)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Services")
            if company.services:
                for service in company.services:
                    st.caption(f"\u2022 {service}")
            else:
                st.caption("None found")
        with col2:
            st.subheader("Technologies")
            if company.technologies:
                for tech in company.technologies:
                    st.caption(f"\u2022 {tech}")
            else:
                st.caption("None found")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Contact")
            if company.emails:
                for email in company.emails:
                    st.caption(f"\U0001f4e7 {email}")
            if company.phones:
                for phone in company.phones:
                    st.caption(f"\U0001f4f1 {phone}")
            if company.address and company.address != "Not Found":
                st.caption(f"\U0001f4cd {company.address}")
        with col2:
            st.subheader("Social")
            if company.social_links:
                for platform, link in company.social_links.items():
                    st.caption(f"\U0001f517 [{platform}]({link})")
            else:
                st.caption("None found")

    def _display_registry(self, company):
        """Indian MCA registry record. Absent for non-Indian companies."""
        if company.cin == "Not Found":
            st.info(
                "No Indian MCA registry record found "
                "(this registry covers Indian companies only)."
            )
            return

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("CIN", company.cin)
        with col2:
            age = company.company_age_years
            st.metric("Age", f"{age} years" if age is not None else "Not Found")
        with col3:
            st.metric("Incorporated", company.incorporation_date)

        st.caption(f"\U0001f3db\ufe0f Registered as: {company.registered_name}")
        if company.registered_email != "Not Found":
            st.caption(f"\U0001f4e7 Registered email: {company.registered_email}")

        if company.directors:
            st.markdown("**Current Directors & Key Managerial Personnel**")
            st.table([
                {
                    "Name": d.name,
                    "Designation": d.designation or "-",
                    "DIN": d.din or "-",
                    "Appointed": d.appointment_date or "-",
                }
                for d in company.directors
            ])
        else:
            st.caption("No current directors listed")

    def _display_reviews(self, reviews):
        """
        Public-review sentiment, positives and negatives side by side, so a
        client can judge whether the company is worth working with.

        Every point carries the review site it came from: points the model
        could not attribute to gathered evidence are dropped upstream, and
        showing the source is what lets a client verify a claim before
        acting on it.
        """
        if reviews.confidence == "none" and not reviews.sources:
            st.info(
                "No public reviews found for this company. This is common for "
                "small, private or recently incorporated vendors, and is not "
                "itself a negative signal."
            )
            return

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Employer rating",
                f"{reviews.employer_rating}/5" if reviews.employer_rating else "N/A",
                help="From employee review sites - what it is like to work AT the company",
            )
        with col2:
            st.metric(
                "Client rating",
                f"{reviews.business_rating}/5" if reviews.business_rating else "N/A",
                help="From B2B and consumer review sites - what it is like to work WITH them",
            )
        with col3:
            st.metric(
                "Evidence",
                reviews.confidence.title(),
                help="How many distinct review sites this is based on",
            )

        if reviews.summary and reviews.summary != "Not Found":
            st.markdown(f"**Verdict:** {reviews.summary}")

        # Thin evidence is easy to over-read, so say so where it will be seen
        # rather than burying it at the bottom.
        if reviews.confidence in ("low", "medium"):
            st.warning(
                "Based on a limited number of review sources. Treat these points "
                "as indicative and check the source links before acting on them."
            )

        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### \u2705 Positive points")
            if reviews.positives:
                for point in reviews.positives:
                    st.markdown(f"\u2022 {point.point}")
                    st.caption(f"{point.category} \u00b7 {point.source_domain}")
            else:
                st.caption("No positive points supported by the review evidence")
        with col2:
            st.markdown("#### \u26a0\ufe0f Negative points")
            if reviews.negatives:
                for point in reviews.negatives:
                    st.markdown(f"\u2022 {point.point}")
                    st.caption(f"{point.category} \u00b7 {point.source_domain}")
            else:
                st.caption("No negative points supported by the review evidence")

        if reviews.sources:
            with st.expander(f"Sources ({len(reviews.sources)} review pages)"):
                for url in reviews.sources:
                    st.caption(f"\U0001f517 {url}")
                st.caption(
                    "Distilled from public search-result snippets on these sites - "
                    "indicative sentiment, not verified review data."
                )


def main():
    app = CompanyIntelligenceApp()
    app.run()


if __name__ == "__main__":
    main()
