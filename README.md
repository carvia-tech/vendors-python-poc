# Company Information Intelligence Engine

A Streamlit demo application that searches for a company's official website, scrapes public information, and uses AI to generate structured intelligence.

## 🎯 Purpose

This is a **demo application for client presentation purposes only**. It demonstrates a workflow for:
- Web search to find official company websites
- Async web scraping with httpx and BeautifulSoup
- Information extraction from multiple pages
- AI-powered analysis with OpenAI-compatible LLMs

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run app.py
```

The application will open at `http://localhost:8501`

## 📁 Project Structure

```
company_intelligence_demo/
│
├── app.py                    # Main Streamlit application
├── config.py                 # Configuration settings
├── models.py                 # Pydantic data models
├── utils.py                  # Utility functions
├── requirements.txt          # Python dependencies
├── README.md                 # This file
│
└── services/
    ├── search.py             # Web search service (DuckDuckGo)
    ├── scraper.py            # Web scraping service (httpx, BeautifulSoup)
    ├── extractor.py          # Information extraction service
    └── ai_analyzer.py        # AI analysis service (LLM)
```

## 🔧 Configuration

### Without AI (Default)

The app works without an API key, but will have limited analysis:
- Web search and scraping work fully
- Contact information extraction works
- Industry and overview will show "Not Found"

### With AI Analysis

1. Enter your OpenAI API key in the sidebar
2. Or set the `LLM_API_KEY` environment variable
3. The app will then use GPT-4o-mini for analysis

## 📊 Workflow

```
User enters company name
         ↓
   Search Web (DuckDuckGo)
         ↓
Find Official Website
         ↓
   Scrape Homepage
         ↓
Find About & Contact Pages
         ↓
  Extract Contact Info
         ↓
   AI Analysis (Optional)
         ↓
  Generate Structured JSON
```

## 📋 Output Schema

```json
{
  "company": {
    "name": "Company Name",
    "industry": "Technology",
    "description": "Brief description",
    "website": "https://example.com",
    "about_page": "https://example.com/about",
    "contact_page": "https://example.com/contact",
    "careers_page": "Not Found",
    "emails": ["contact@example.com"],
    "phones": ["+1-555-1234"],
    "address": "123 Main St, City, Country",
    "services": ["Service 1", "Service 2"],
    "technologies": ["Python", "React"],
    "social_links": {
      "linkedin": "https://linkedin.com/company/example",
      "twitter": "https://twitter.com/example"
    },
    "overview": "Detailed company overview..."
  },
  "metadata": {
    "source": "Official Website",
    "confidence": 100,
    "retrieved_at": "2024-01-01T00:00:00",
    "status": "Success"
  }
}
```

## 🔍 Features

- **Async Web Search**: Uses DuckDuckGo Search (free, no API key needed)
- **Async Scraping**: Concurrent page fetching with httpx
- **Smart Filtering**: Excludes Wikipedia, LinkedIn, Crunchbase, etc.
- **Contact Extraction**: Emails, phones, addresses
- **Social Links**: LinkedIn, Twitter, Facebook, GitHub
- **AI Analysis**: Structured JSON output with GPT-4o-mini
- **Progress Indicators**: Real-time progress updates
- **Expandable Sections**: Logs, extracted text, JSON output

## ⚠️ Limitations

This is a **demo application**:

- No database
- No authentication
- No caching
- No production optimizations
- Basic error handling
- Limited retry logic
- Single-user only

## 🛠️ Tech Stack

- **Python 3.12**
- **Streamlit** - Web UI
- **httpx** - Async HTTP client
- **BeautifulSoup4** - HTML parsing
- **DuckDuckGo Search** - Web search
- **Pydantic** - Data validation
- **OpenAI API** - AI analysis (optional)

## 📝 Examples to Try

- Microsoft
- Infosys
- Google
- Amazon
- Tesla

## 🤝 Contributing

This is a demo project. For production use, you would need:
- Database integration
- Caching layer (Redis)
- Rate limiting
- Better error handling
- Logging infrastructure
- Monitoring
- Tests

## 📄 License

Demo Project - For Presentation Purposes Only
