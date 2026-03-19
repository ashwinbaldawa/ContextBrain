"""
Embedding service — generates vector embeddings for API descriptions.

Uses Voyage AI (voyage-3) by default. Falls back to a simple
hash-based embedding for local development without an API key.
"""

import hashlib
import struct
import logging
from typing import Optional

from src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Lazy-loaded client
_voyage_client = None


def _get_voyage_client():
    """Lazy-initialize the Voyage AI client."""
    global _voyage_client
    if _voyage_client is None:
        try:
            import voyageai
            _voyage_client = voyageai.Client()
            logger.info("Voyage AI client initialized")
        except Exception as e:
            logger.warning(f"Voyage AI not available: {e}. Using fallback embeddings.")
            _voyage_client = "fallback"
    return _voyage_client


async def generate_embedding(text: str) -> list[float]:
    """
    Generate a vector embedding for the given text.

    Uses Voyage AI if available, otherwise falls back to a deterministic
    hash-based embedding (suitable for development/testing only).
    """
    if not text or not text.strip():
        return [0.0] * settings.embedding_dimensions

    client = _get_voyage_client()

    if client != "fallback":
        try:
            result = client.embed([text], model=settings.embedding_model)
            return result.embeddings[0]
        except Exception as e:
            logger.error(f"Voyage AI embedding failed: {e}. Using fallback.")

    # Fallback: deterministic hash-based embedding (dev/testing only)
    return _hash_embedding(text, settings.embedding_dimensions)


async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
    client = _get_voyage_client()

    if client != "fallback":
        try:
            # Voyage AI supports batching
            result = client.embed(texts, model=settings.embedding_model)
            return result.embeddings
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}. Using fallback.")

    return [_hash_embedding(t, settings.embedding_dimensions) for t in texts]


def _hash_embedding(text: str, dimensions: int) -> list[float]:
    """
    Generate a deterministic pseudo-embedding from text using hashing.
    NOT for production — only for development without an embedding API.
    Texts with similar words will NOT have similar embeddings.
    """
    embedding = []
    for i in range(dimensions):
        hash_input = f"{text}:{i}".encode("utf-8")
        h = hashlib.sha256(hash_input).digest()
        # Convert first 4 bytes to a float between -1 and 1
        val = struct.unpack("f", h[:4])[0]
        # Normalize to [-1, 1]
        normalized = max(-1.0, min(1.0, val / 1e10))
        embedding.append(normalized)

    # L2 normalize
    norm = sum(x * x for x in embedding) ** 0.5
    if norm > 0:
        embedding = [x / norm for x in embedding]

    return embedding
