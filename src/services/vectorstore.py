"""
ChromaDB vector store service.

Manages the ChromaDB client, collections, and CRUD operations
for API and endpoint embeddings. Designed with a clean interface
so swapping to Vertex AI Vector Search later is straightforward.
"""

import logging

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Lazy-loaded clients
_chroma_client = None
_api_collection = None
_endpoint_collection = None


def get_chroma_client() -> chromadb.ClientAPI:
    """Get or create the ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        if settings.chroma_mode == "http":
            _chroma_client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
            )
            logger.info(f"ChromaDB connected via HTTP: {settings.chroma_host}:{settings.chroma_port}")
        else:
            _chroma_client = chromadb.PersistentClient(
                path=settings.chroma_persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            logger.info(f"ChromaDB using local storage: {settings.chroma_persist_dir}")
    return _chroma_client


def get_api_collection() -> chromadb.Collection:
    """Get or create the API-level embeddings collection."""
    global _api_collection
    if _api_collection is None:
        client = get_chroma_client()
        _api_collection = client.get_or_create_collection(
            name=f"{settings.chroma_collection_name}_apis",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"ChromaDB API collection ready: {_api_collection.name} ({_api_collection.count()} docs)")
    return _api_collection


def get_endpoint_collection() -> chromadb.Collection:
    """Get or create the endpoint-level embeddings collection."""
    global _endpoint_collection
    if _endpoint_collection is None:
        client = get_chroma_client()
        _endpoint_collection = client.get_or_create_collection(
            name=f"{settings.chroma_collection_name}_endpoints",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"ChromaDB endpoint collection ready: {_endpoint_collection.name} ({_endpoint_collection.count()} docs)")
    return _endpoint_collection


def upsert_api_embedding(
    api_id: str,
    embedding: list[float],
    document: str,
    metadata: dict | None = None,
):
    """Store or update an API embedding in ChromaDB."""
    collection = get_api_collection()
    collection.upsert(
        ids=[api_id],
        embeddings=[embedding],
        documents=[document],
        metadatas=[metadata or {}],
    )


def upsert_endpoint_embedding(
    endpoint_id: str,
    api_id: str,
    embedding: list[float],
    document: str,
    metadata: dict | None = None,
):
    """Store or update an endpoint embedding in ChromaDB."""
    collection = get_endpoint_collection()
    meta = metadata or {}
    meta["api_id"] = api_id
    collection.upsert(
        ids=[endpoint_id],
        embeddings=[embedding],
        documents=[document],
        metadatas=[meta],
    )


def search_apis(
    query_embedding: list[float],
    top_k: int = 5,
    where: dict | None = None,
) -> dict:
    """
    Search API embeddings by vector similarity.

    Returns ChromaDB query result with ids, distances, documents, metadatas.
    """
    collection = get_api_collection()
    kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": min(top_k, collection.count()) if collection.count() > 0 else top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    return collection.query(**kwargs)


def search_endpoints(
    query_embedding: list[float],
    top_k: int = 10,
    where: dict | None = None,
) -> dict:
    """
    Search endpoint embeddings by vector similarity.

    Returns ChromaDB query result with ids, distances, documents, metadatas.
    """
    collection = get_endpoint_collection()
    kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": min(top_k, collection.count()) if collection.count() > 0 else top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    return collection.query(**kwargs)


def delete_api(api_id: str):
    """Remove an API and its endpoints from ChromaDB."""
    try:
        api_col = get_api_collection()
        api_col.delete(ids=[api_id])
    except Exception as e:
        logger.warning(f"Failed to delete API {api_id} from ChromaDB: {e}")

    try:
        ep_col = get_endpoint_collection()
        # Delete all endpoints belonging to this API
        ep_col.delete(where={"api_id": api_id})
    except Exception as e:
        logger.warning(f"Failed to delete endpoints for API {api_id}: {e}")


def get_collection_stats() -> dict:
    """Return counts for monitoring."""
    return {
        "api_count": get_api_collection().count(),
        "endpoint_count": get_endpoint_collection().count(),
    }
