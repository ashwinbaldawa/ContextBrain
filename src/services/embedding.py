"""
Embedding service — generates vector embeddings using Google Gemini.

Uses text-embedding-004 by default (768 dimensions).
Designed for easy future migration to Vertex AI embeddings.
"""

import logging
import hashlib
import struct

import google.generativeai as genai

from src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Embedding dimensions by model
MODEL_DIMENSIONS = {
    "text-embedding-004": 768,
    "embedding-001": 768,
}

_configured = False


def _ensure_configured():
    """Configure the Gemini API client once."""
    global _configured
    if not _configured and settings.google_api_key:
        genai.configure(api_key=settings.google_api_key)
        _configured = True
        logger.info(f"Gemini configured with embedding model: {settings.gemini_embedding_model}")


def get_embedding_dimensions() -> int:
    """Return the dimensionality of the current embedding model."""
    return MODEL_DIMENSIONS.get(settings.gemini_embedding_model, 768)


def generate_embedding(text: str) -> list[float]:
    """
    Generate a vector embedding for the given text using Gemini.

    Falls back to a deterministic hash-based embedding if no API key is set.
    """
    if not text or not text.strip():
        return [0.0] * get_embedding_dimensions()

    if not settings.google_api_key:
        logger.warning("No GOOGLE_API_KEY — using fallback hash embeddings (dev only)")
        return _hash_embedding(text, get_embedding_dimensions())

    _ensure_configured()

    try:
        result = genai.embed_content(
            model=f"models/{settings.gemini_embedding_model}",
            content=text,
            task_type="retrieval_document",
        )
        return result["embedding"]
    except Exception as e:
        logger.error(f"Gemini embedding failed: {e}. Using fallback.")
        return _hash_embedding(text, get_embedding_dimensions())


def generate_embedding_for_query(text: str) -> list[float]:
    """
    Generate an embedding optimized for search queries.
    Uses task_type="retrieval_query" for better search relevance.
    """
    if not text or not text.strip():
        return [0.0] * get_embedding_dimensions()

    if not settings.google_api_key:
        return _hash_embedding(text, get_embedding_dimensions())

    _ensure_configured()

    try:
        result = genai.embed_content(
            model=f"models/{settings.gemini_embedding_model}",
            content=text,
            task_type="retrieval_query",
        )
        return result["embedding"]
    except Exception as e:
        logger.error(f"Gemini query embedding failed: {e}. Using fallback.")
        return _hash_embedding(text, get_embedding_dimensions())


def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
    if not settings.google_api_key:
        return [_hash_embedding(t, get_embedding_dimensions()) for t in texts]

    _ensure_configured()

    try:
        # Gemini supports batch embedding
        result = genai.embed_content(
            model=f"models/{settings.gemini_embedding_model}",
            content=texts,
            task_type="retrieval_document",
        )
        return result["embedding"]
    except Exception as e:
        logger.error(f"Batch embedding failed: {e}. Using fallback.")
        return [_hash_embedding(t, get_embedding_dimensions()) for t in texts]


def _hash_embedding(text: str, dimensions: int) -> list[float]:
    """
    Deterministic pseudo-embedding from text using hashing.
    NOT for production — only for development without an API key.
    """
    embedding = []
    for i in range(dimensions):
        hash_input = f"{text}:{i}".encode("utf-8")
        h = hashlib.sha256(hash_input).digest()
        val = struct.unpack("f", h[:4])[0]
        normalized = max(-1.0, min(1.0, val / 1e10))
        embedding.append(normalized)

    norm = sum(x * x for x in embedding) ** 0.5
    if norm > 0:
        embedding = [x / norm for x in embedding]
    return embedding
