"""
FastAPI application for the Company Intelligence Engine.

This is the main entry point for the FastAPI microservice.
Run with: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from api.routes.enrichment import router as enrichment_router
from api.routes.search import router as search_router
from utils import setup_logging

logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan handler for application startup and shutdown events.
    """
    # Startup
    logger.info("=" * 60)
    logger.info(f"{settings.app_name} v{settings.app_version}")
    logger.info(f"Starting FastAPI server on {settings.api_host}:{settings.api_port}")
    logger.info(f"LLM Mode: {'Enabled' if settings.llm_api_key else 'Disabled (use sidebar/api_key)'}")
    logger.info("=" * 60)
    yield
    # Shutdown
    logger.info("Shutting down Company Intelligence Engine...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A microservice that searches, scrapes, and analyzes company information from official websites. "
                "Provides structured JSON output for Java backend integration.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware - Allow Java backend to call this service
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(enrichment_router, prefix="/api", tags=["Enrichment"])
app.include_router(search_router, prefix="/api", tags=["Search"])

