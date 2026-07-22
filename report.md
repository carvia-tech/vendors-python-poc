# Company Information Intelligence Module
## Technical Proposal & Implementation Plan

### 1. Executive Summary

We propose to build an intelligent Company Information Module for Career24/LinkageIT that automatically enriches company profiles using AI-powered data extraction from multiple public sources. This module will eliminate manual data entry, ensure data accuracy through multi-source verification, and provide comprehensive company insights including registered details (GST, PAN, MSME), technology stack, employee count, and hiring trends.

---

### 2. Business Problem

Current Challenges:
- Manual data entry for company profiles is time-consuming
- No automated verification of company credentials (GST, PAN, MSME)
- Limited visibility into company technology stack and hiring patterns
- Data inconsistency across vendor records
- No confidence scoring on data accuracy

---

### 3. Proposed Solution

**Company Information Intelligence Engine** - An AI-powered module that:

1. Accepts a company name as input
2. Searches multiple trusted public sources in parallel
3. Aggregates, validates, and fuses data from all sources
4. Returns structured JSON with comprehensive company profile
5. Provides confidence scores and source tracking for every data point

---

### 4. How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INPUT                                │
│              "Linkage IT Private Limited"                   │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────┐
│              MULTI-SOURCE SEARCH ENGINE                      │
├──────────────┬──────────────┬──────────────┬───────────────┤
│   Official   │    LinkedIn  │   Government │    Business   │
│   Website    │    Company   │   Records    │  Directories  │
│              │    Page      │  (MCA/GST)   │  (Crunchbase) │
└──────────────┴──────────────┴──────────────┴───────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────┐
│              AI-POWERED DATA EXTRACTION                       │
│  • Technology Stack Detection                               │
│  • Service Identification                                   │
│  • Contact Email Categorization                              │
│  • Address Parsing                                           │
│  • Employee Count Estimation                                │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────┐
│              DATA FUSION & VALIDATION                         │
│  • Source Priority (Official > Govt > LinkedIn > Directories)│
│  • Conflict Resolution                                       │
│  • Confidence Scoring                                        │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────┐
│              STRUCTURED JSON OUTPUT                          │
│  Complete company profile with 15+ data categories          │
└─────────────────────────────────────────────────────────────┘
```

---

### 5. What Gets Returned (Complete Data Structure)

| Category | Data Fields |
|----------|-------------|
| **Company Identity** | Name, Legal Name, Type, Year Established, Status, Industry |
| **Web Presence** | Official Website, Careers Page, Contact Page |
| **LinkedIn** | Company URL, Followers, Employee Count |
| **Address** | Building, Street, Area, City, State, Country, Postal Code |
| **Contact** | HR Email, Sales Email, Support Email, Board Phone, Reception |
| **Company Size** | Total Employees, LinkedIn Employees, Global, India |
| **Technology Stack** | Top 20 technologies (Java, React, AWS, Azure, etc.) |
| **Business Services** | IT Staffing, Software Dev, Cloud, AI, Consulting, ERP, CRM |
| **India-Specific** | GSTIN, PAN, MSME/Udyam Number (when publicly available) |
| **Social Media** | LinkedIn, Twitter, Facebook, Instagram, YouTube, GitHub |
| **Company Domains** | Corporate, Career, Customer, Support, Developer Portals |
| **Hiring Intelligence** | Top Skills, Locations, Current Hiring Status |
| **Company Overview** | AI-generated summary of business and capabilities |

---

### 6. Role of AI/LLM in This Module

The LLM (Large Language Model) is used for intelligent extraction and analysis:

| Use Case | What AI Does |
|----------|--------------|
| **Technology Detection** | Analyzes website, careers page, job descriptions to identify top 20 technologies used |
| **Service Categorization** | Reads company content to classify services (Staffing, Development, Consulting, etc.) |
| **Email Categorization** | Intelligently categorizes emails as HR, Sales, or Support based on context |
| **Address Parsing** | Extracts structured address components (street, city, state, pincode) from unstructured text |
| **Company Overview** | Generates concise 3-4 sentence summary from multiple data sources |
| **Data Validation** | Cross-references information from different sources to flag inconsistencies |

**Why AI?**
- Handles unstructured data (websites, descriptions, job postings)
- Adapts to different website formats automatically
- Reduces manual rule maintenance
- Provides confidence scoring on extracted data

---

### 7. Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              CAREER24 / LINKAGEIT                           │
│              (React Frontend + Java Backend)                │
└──────────────────────────────┬──────────────────────────────┘
                               │ REST API
                               ↓
┌─────────────────────────────────────────────────────────────┐
│         COMPANY INTELLIGENCE MODULE                         │
│              (Python Microservice)                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Search    │  │  Scraper    │  │   Source    │         │
│  │   Engine    │  │  Service    │  │Connectors   │         │
│  │             │  │             │  │(LinkedIn,   │         │
│  │  Google     │  │  httpx +    │  │Crunchbase,  │         │
│  │  DDG        │  │ BeautifulSoup│ │Gov Records) │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Data      │  │     LLM     │  │    Cache    │         │
│  │  Fusion     │  │  Analysis   │  │   (Redis)   │         │
│  │             │  │             │  │             │         │
│  │ Priority    │  │  OpenAI     │  │  7-30 day   │         │
│  │  Scoring    │  │  Compatible │  │    TTL      │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Queue     │  │  Database   │  │   API       │         │
│  │  System     │  │ PostgreSQL  │  │  FastAPI    │         │
│  │             │  │             │  │             │         │
│  │  Celery     │  │  + Mongo    │  │  /enrich    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

### 8. Data Sources & Priority

| Priority | Source | Data Retrieved |
|----------|--------|-----------------|
| **1 (Highest)** | Official Website | All core company data, services, technologies |
| **2** | Government Records (MCA/GST) | Legal name, GSTIN, PAN, MSME, Address |
| **3** | LinkedIn Company Page | Employees, Description, Industry, Followers |
| **4** | Careers/Jobs Page | Technology stack, hiring skills, locations |
| **5** | Business Directories | Validation, additional contacts, funding |

**Note:** When sources conflict, higher priority source is used. All sources are logged for audit trail.

---

### 9. API Integration Points

```java
// Java Backend calls Python Module
POST http://company-intelligence-service/api/enrich
{
  "companyName": "Linkage IT Private Limited"
}

// Response
{
  "company_name": "Linkage IT Private Limited",
  "legal_name": "Linkage IT Private Limited",
  "website": "https://linkageit.com",
  "linkedin_url": "https://linkedin.com/company/linkage-it",
  "registered_address": {
    "building": "",
    "street": "Sector 63",
    "city": "Noida",
    "state": "Uttar Pradesh",
    "country": "India",
    "postal_code": "201301"
  },
  "year_established": "2015",
  "industry": "Information Technology & Services",
  "employee_count": {
    "total": "150-200",
    "linkedin": "180",
    "confidence": 0.85
  },
  "top_skills": [
    {"skill": "Java", "confidence": 0.95},
    {"skill": "ReactJS", "confidence": 0.90},
    {"skill": "AWS", "confidence": 0.88}
  ],
  "company_email": "info@linkageit.com",
  "gstin": "09AAPCL1234L1Z5",
  "pan": "AAPCL1234L",
  "msme_registered": "Yes",
  "sources": ["official_website", "linkedin", "mca_records"],
  "retrieved_at": "2025-01-15T10:30:00Z",
  "confidence_score": 0.87
}
```

---

### 10. Implementation Timeline

| Phase | Duration | Key Deliverables | Status |
|-------|----------|------------------|--------|
| **Phase 1** | Weeks 1-3 | • Search Engine Integration<br>• Web Scraper<br>• Basic Data Extraction | Pending |
| **Phase 2** | Weeks 4-5 | • Source Connectors (LinkedIn, Gov Records)<br>• Data Fusion Engine<br>• Priority-based Merging | Pending |
| **Phase 3** | Weeks 6-7 | • LLM Integration<br>• Technology Stack Detection<br>• Service Categorization | Pending |
| **Phase 4** | Week 8 | • Cache System (Redis)<br>• Queue System (Celery)<br>• Database Schema | Pending |
| **Phase 5** | Week 9 | • REST API (FastAPI)<br>• Java Backend Integration<br>• Testing & QA | Pending |

**Total Duration: 9 Weeks**

---

### 11. Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Language** | Python 3.12+ | AI/ML ecosystem compatibility |
| **Web Framework** | FastAPI | High-performance API |
| **Async HTTP** | httpx | Concurrent web scraping |
| **HTML Parsing** | BeautifulSoup4 | Web content extraction |
| **Search** | DuckDuckGo/Google | Company discovery |
| **LLM** | OpenAI API | AI-powered analysis |
| **Cache** | Redis | Result caching & queue |
| **Queue** | Celery | Background job processing |
| **Database** | PostgreSQL + MongoDB | Structured + document storage |
| **Integration** | REST API | Java backend communication |

---

### 12. Compliance & Best Practices

✅ **Respects robots.txt** - Only scrapes allowed pages
✅ **Rate limiting** - Polite crawling with delays
✅ **Source attribution** - Every data point tracks its source
✅ **No data fabrication** - Returns "Not Found" instead of guessing
✅ **Privacy compliant** - Uses only publicly available data
✅ **Audit trail** - Timestamps and source logging
✅ **Cache with expiry** - 7-30 day refresh for data freshness

---

### 13. Benefits for Career24/LinkageIT

| Benefit | Impact |
|---------|--------|
| **Automated Enrichment** | Zero manual data entry for new companies |
| **Data Verification** | GST, PAN, MSME validation instantly available |
| **Skill Matching** | Technology stack enables better candidate-company matching |
| **Market Intelligence** | Track hiring trends and skill demand |
| **Data Quality** | Multi-source verification ensures accuracy |
| **Time Savings** | 80% reduction in profile creation time |

---

### 14. Next Steps

1. ✅ Approve this proposal and data structure
2. ⬜ Set up development environment and infrastructure
3. ⬜ Begin Phase 1 development (Search + Scraper)
4. ⬜ Weekly progress reviews
5. ⬜ UAT and integration with Career24/LinkageIT

---

### 15. Investment Summary

| Item | Description |
|------|-------------|
| **Development Time** | 9 weeks |
| **Technology Stack** | Python, AI/LLM, Redis, PostgreSQL |
| **Integration Effort** | REST API - minimal changes to Java backend |
| **Maintenance** | Low - automated with cache refresh |

---

### Appendix: Sample Output JSON

[Complete JSON structure provided in technical specification]

---

**Document Version:** 1.0
**Prepared For:** Career24/LinkageIT
**Prepared By:** Python + AI Developer
**Date:** January 2025
