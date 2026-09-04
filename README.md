# Company Information Intelligence Engine (FastAPI)

A FastAPI microservice that searches for a company's official website, scrapes public information, and uses AI to generate structured intelligence. Designed as a helper module for Java backend integration.

## 🎯 Purpose

This **FastAPI microservice** provides REST API endpoints that Java backends can call to enrich company profiles. The response JSON is directly consumable by frontend applications.

### Java Backend Integration

```java
// Java calls the Python microservice
POST http://python-service:8000/api/enrich
Body: { "company_name": "Infosys" }

// Response is ready-to-use JSON
{
  "success": true,
  "data": {
    "company": { ... full company info ... },
    "metadata": { ... retrieval metadata ... }
  }
}
```

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- **API**: `http://localhost:8000/api/health`
- **Docs**: `http://localhost:8000/docs` (Swagger UI)
- **Redoc**: `http://localhost:8000/redoc`

## 📁 Project Structure

```
company_intelligence_demo/
│
├── api/                     # FastAPI application package
│   ├── __init__.py
│   ├── main.py              # FastAPI app with CORS, lifespan
│   ├── dependencies.py      # Service initialization & enrichment pipeline
│   └── routes/
│       ├── __init__.py
│       └── enrichment.py    # POST /api/enrich, GET /api/health
│
├── schemas/                  # API request/response schemas
│   ├── __init__.py
│   ├── request.py            # EnrichmentRequest
│   └── response.py           # HealthResponse, EnrichmentResponse
│
├── services/                 # Core business logic (reused)
│   ├── __init__.py
│   ├── search.py             # Web search (DuckDuckGo)
│   ├── scraper.py            # Web scraping (httpx, BeautifulSoup)
│   ├── extractor.py          # Information extraction
│   └── ai_analyzer.py        # AI analysis (LLM)
│
├── config.py                 # Configuration settings
├── models.py                 # Pydantic data models
├── utils.py                  # Utility functions
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── start.sh                  # Linux/Mac startup script
└── start.bat                 # Windows startup script
```

## 🔧 API Endpoints

### `GET /api/health`

Health check endpoint.

```json
{
  "status": "ok",
  "service": "Company Information Intelligence Engine",
  "version": "1.0.0",
  "timestamp": "2026-07-21T10:30:00Z"
}
```

### `POST /api/enrich`

Enrich company information by searching, scraping, and analyzing.

**Request:**
```json
{
  "company_name": "Infosys"
}
```

The API key is configured on the server through `LLM_API_KEY` in the repository-level `.env`; it is never sent in an API request. Without it, AI analysis is skipped.

**Response:**
```json
{
  "success": true,
  "data": {
    "company": {
      "name": "Infosys Limited",
      "website": "https://www.infosys.com",
      "industry": "Information Technology and Consulting",
      "description": "Infosys is a global technology company providing digital transformation, consulting, and outsourcing services.",
      "about_page": "https://www.infosys.com/about",
      "contact_page": "https://www.infosys.com/contact",
      "careers_page": "https://career.infosys.com",
      "emails": ["Not Found"],
      "phones": ["+91-80-2852-0261"],
      "address": "Electronics City, Hosur Road, Bengaluru, Karnataka, India",
      "services": ["Digital Transformation", "Cloud Services"],
      "technologies": ["Azure", "AWS", "SAP"],
      "social_links": {
        "linkedin": "https://www.linkedin.com/company/infosys",
        "youtube": "https://www.youtube.com/@Infosys",
        "twitter": "https://twitter.com/Infosys"
      },
      "overview": "Infosys is an Indian multinational IT services company..."
    },
    "metadata": {
      "source": "Official Website",
      "confidence": 100,
      "retrieved_at": "2026-07-21T10:30:00Z",
      "status": "Success"
    }
  },
  "error": null
}
```

## 🔧 Configuration

### Without AI (Default)
The service works without an API key. Industry and overview will show "Not Found".

### With AI Analysis
Set `LLM_API_KEY` in the repository-level `.env` file.
3. Uses GPT-4o-mini for intelligent analysis

All settings can be configured via `.env` file or environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_API_KEY` | None | OpenAI API key |
| `LLM_MODEL` | gpt-4o-mini | LLM model to use |
| `API_PORT` | 8000 | FastAPI server port |
| `API_HOST` | 0.0.0.0 | Bind address |
| `CORS_ORIGINS` | ["*"] | Allowed CORS origins |

## 📊 Workflow

```
Java Backend
    │
    │  POST /api/enrich { company_name }
    ▼
FastAPI Microservice
    │
    ├── 1. Search Web (DuckDuckGo)
    ├── 2. Find Official Website
    ├── 3. Scrape Homepage
    ├── 4. Find About & Contact Pages
    ├── 5. Extract Contact Info
    ├── 6. AI Analysis (if API key provided)
    └── 7. Return Structured JSON
    │
    ▼
Java Backend receives JSON → passes to Frontend
```

## 🔍 Features

- **REST API**: Clean endpoints for Java integration
- **Async Processing**: Non-blocking async/await throughout
- **CORS Enabled**: Ready for cross-origin frontend calls
- **Detailed Logging**: Step-by-step progress with timestamps
- **Error Handling**: Graceful failures with descriptive messages
- **Swagger Docs**: Auto-generated OpenAPI documentation at `/docs`
- **Scalable Architecture**: Easily add LinkedIn, Government modules later

## 🛠️ Tech Stack

- **Python 3.12**
- **FastAPI** - REST API framework
- **httpx** - Async HTTP client
- **BeautifulSoup4** - HTML parsing
- **DuckDuckGo Search** - Web search
- **Pydantic** - Data validation & schemas
- **OpenAI API** - AI analysis (optional)

## 📝 Examples

```bash
# Health check
curl http://localhost:8000/api/health

# Enrich a company (no AI)
curl -X POST http://localhost:8000/api/enrich \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Infosys"}'

# Enrich with AI
curl -X POST http://localhost:8000/api/enrich \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Infosys"}'
```

## 🏗️ Adding New Data Sources (Scalability)

The architecture supports adding new data sources easily:

1. Create `services/sources/linkedin.py`
2. Implement a `LinkedInSource` class
3. Add it to the pipeline in `api/dependencies.py` Example structure:
```
services/
├── sources/              # Future: pluggable data sources
│   ├── __init__.py
│   ├── linkedin.py       # LinkedIn company page scraper
│   └── government.py     # MCA/GST records lookup
└── ...existing services
```

## 📄 License

Demo Project - For Presentation Purposes Only
