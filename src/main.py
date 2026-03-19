"""APIBrain — FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.routers import ingest, search, chat, annotations

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("🧠 APIBrain starting up...")
    logger.info(f"   Environment: {settings.app_env}")
    logger.info(f"   Database: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'configured'}")
    logger.info(f"   Anthropic API: {'configured' if settings.anthropic_api_key else 'NOT configured (AI features disabled)'}")
    yield
    logger.info("🧠 APIBrain shutting down...")


app = FastAPI(
    title="APIBrain",
    description="AI-powered API Discovery Platform for Enterprise Organizations",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(ingest.router)
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(annotations.router)


@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "apibrain",
        "version": "0.1.0",
        "ai_enabled": bool(settings.anthropic_api_key),
    }
