"""
Search service — hybrid search using ChromaDB (vector) + PostgreSQL (relational).

Flow:
1. Embed the query using Gemini (with retrieval_query task type)
2. Search ChromaDB for similar APIs and endpoints
3. Fetch full relational data from PostgreSQL
4. Merge, deduplicate, and rank results
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config import get_settings
from src.models import APICatalog, APIEndpoint, Annotation
from src.services.embedding import generate_embedding_for_query
from src.services import vectorstore

logger = logging.getLogger(__name__)
settings = get_settings()


async def search_apis(
    db: AsyncSession,
    query: str,
    domain: str | None = None,
    status: str | None = None,
    top_k: int = 5,
) -> list[dict]:
    """
    Search for APIs using hybrid vector + relational approach.

    1. Embed the query
    2. Search ChromaDB at API level and endpoint level
    3. Fetch full details from PostgreSQL
    4. Merge and rank
    """
    query_embedding = generate_embedding_for_query(query)

    # --- Search ChromaDB: API level ---
    api_where = {}
    if domain:
        api_where["domain"] = domain
    if status:
        api_where["status"] = status

    api_results = vectorstore.search_apis(
        query_embedding=query_embedding,
        top_k=top_k,
        where=api_where if api_where else None,
    )

    # --- Search ChromaDB: Endpoint level ---
    endpoint_results = vectorstore.search_endpoints(
        query_embedding=query_embedding,
        top_k=top_k * 2,
    )

    # --- Collect unique API IDs with scores ---
    api_scores: dict[str, dict] = {}

    # API-level results
    if api_results and api_results["ids"] and api_results["ids"][0]:
        for i, api_id in enumerate(api_results["ids"][0]):
            distance = api_results["distances"][0][i] if api_results["distances"] else 1.0
            score = 1.0 - distance  # ChromaDB cosine distance → similarity
            score *= 1.1  # 10% boost for API-level match
            api_scores[api_id] = {
                "score": score,
                "match_reason": "API description matches your query",
            }

    # Endpoint-level results — bubble up to parent API
    if endpoint_results and endpoint_results["ids"] and endpoint_results["ids"][0]:
        for i, ep_id in enumerate(endpoint_results["ids"][0]):
            meta = endpoint_results["metadatas"][0][i] if endpoint_results["metadatas"] else {}
            api_id = meta.get("api_id", "")
            if not api_id:
                continue

            distance = endpoint_results["distances"][0][i] if endpoint_results["distances"] else 1.0
            score = 1.0 - distance

            if api_id in api_scores:
                # Already found via API-level — take the higher score
                existing = api_scores[api_id]
                if score > existing["score"]:
                    existing["score"] = score
                existing["match_reason"] += " | Also matched at endpoint level"
            else:
                method = meta.get("method", "")
                path = meta.get("path", "")
                api_scores[api_id] = {
                    "score": score,
                    "match_reason": f"Endpoint {method} {path} matches your query",
                }

    # --- Fetch full data from PostgreSQL ---
    results = []
    sorted_apis = sorted(api_scores.items(), key=lambda x: x[1]["score"], reverse=True)[:top_k]

    for api_id_str, score_info in sorted_apis:
        try:
            api_uuid = UUID(api_id_str)
        except ValueError:
            continue

        # Fetch API with endpoints and annotations
        stmt = (
            select(APICatalog)
            .options(selectinload(APICatalog.endpoints), selectinload(APICatalog.annotations))
            .where(APICatalog.id == api_uuid)
        )
        result = await db.execute(stmt)
        api = result.scalar_one_or_none()

        if not api:
            continue

        # Apply domain/status filters (in case ChromaDB metadata was incomplete)
        if domain and api.domain != domain:
            continue
        if status and api.status != status:
            continue

        results.append({
            "api": api,
            "endpoints": list(api.endpoints),
            "annotations": list(api.annotations),
            "relevance_score": max(0.0, min(1.0, score_info["score"])),
            "match_reason": score_info["match_reason"],
        })

    return results


async def get_all_apis(db: AsyncSession) -> list[APICatalog]:
    """Fetch all APIs in the catalog."""
    stmt = (
        select(APICatalog)
        .options(selectinload(APICatalog.endpoints), selectinload(APICatalog.annotations))
        .order_by(APICatalog.name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_api_by_id(db: AsyncSession, api_id: UUID) -> APICatalog | None:
    """Fetch a single API with its endpoints and annotations."""
    stmt = (
        select(APICatalog)
        .options(selectinload(APICatalog.endpoints), selectinload(APICatalog.annotations))
        .where(APICatalog.id == api_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
