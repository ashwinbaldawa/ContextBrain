"""ContextBrain — FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.routers import ingest, search, chat, annotations

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("🧠 ContextBrain starting up...")
    logger.info(f"   Environment: {settings.app_env}")
    logger.info(f"   PostgreSQL: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'configured'}")
    logger.info(f"   ChromaDB: {settings.chroma_mode} ({settings.chroma_persist_dir if settings.chroma_mode == 'local' else f'{settings.chroma_host}:{settings.chroma_port}'})")
    logger.info(f"   Gemini LLM: {settings.gemini_llm_model}")
    logger.info(f"   Gemini Embeddings: {settings.gemini_embedding_model}")
    logger.info(f"   Google API Key: {'configured' if settings.google_api_key else 'NOT configured (AI features disabled)'}")

    # Initialize ChromaDB collections on startup
    from src.services.vectorstore import get_collection_stats
    stats = get_collection_stats()
    logger.info(f"   ChromaDB collections: {stats['api_count']} APIs, {stats['endpoint_count']} endpoints")

    yield
    logger.info("🧠 ContextBrain shutting down...")


app = FastAPI(
    title="ContextBrain",
    description="AI-powered Context Discovery Platform — APIs, Schemas, Knowledge",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(annotations.router)


@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    from src.services.vectorstore import get_collection_stats
    stats = get_collection_stats()
    return {
        "status": "healthy",
        "service": "contextbrain",
        "version": "0.2.0",
        "ai_enabled": bool(settings.google_api_key),
        "llm_model": settings.gemini_llm_model,
        "embedding_model": settings.gemini_embedding_model,
        "vector_store": "chromadb",
        "chroma_mode": settings.chroma_mode,
        "chroma_apis": stats["api_count"],
        "chroma_endpoints": stats["endpoint_count"],
    }
