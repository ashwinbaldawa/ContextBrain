"""
Search service — semantic + hybrid search across the API catalog.

Uses pgvector cosine similarity combined with keyword matching
to find the most relevant APIs for a given query.
"""

import logging
from uuid import UUID

from sqlalchemy import select, func, or_, cast, String, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config import get_settings
from src.models import APICatalog, APIEndpoint, Annotation
from src.services.embedding import generate_embedding

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
    Search for APIs using a hybrid approach:
    1. Semantic search (vector similarity on API descriptions)
    2. Semantic search (vector similarity on endpoint descriptions)
    3. Keyword matching (API name, endpoint path, descriptions)
    4. Merge and re-rank results

    Returns a list of results with API details, matching endpoints,
    annotations, and relevance scores.
    """
    query_embedding = await generate_embedding(query)

    # --- Semantic search on APIs ---
    api_results = await _search_api_level(db, query_embedding, query, domain, status, top_k)

    # --- Semantic search on Endpoints ---
    endpoint_results = await _search_endpoint_level(db, query_embedding, query, domain, status, top_k)

    # --- Merge results ---
    merged = _merge_results(api_results, endpoint_results, top_k)

    # --- Fetch annotations for top results ---
    for result in merged:
        annotations = await _get_annotations(db, result["api"].id)
        result["annotations"] = annotations

    return merged


async def _search_api_level(
    db: AsyncSession,
    query_embedding: list[float],
    query_text: str,
    domain: str | None,
    status: str | None,
    top_k: int,
) -> list[dict]:
    """Search at the API level using vector similarity + keyword."""
    # Vector similarity using cosine distance
    similarity = (1 - APICatalog.embedding.cosine_distance(query_embedding)).label("similarity")

    stmt = (
        select(APICatalog, similarity)
        .options(selectinload(APICatalog.endpoints))
        .where(APICatalog.embedding.isnot(None))
    )

    if domain:
        stmt = stmt.where(APICatalog.domain == domain)
    if status:
        stmt = stmt.where(APICatalog.status == status)

    stmt = stmt.order_by(similarity.desc()).limit(top_k)

    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "api": row[0],
            "endpoints": list(row[0].endpoints),
            "relevance_score": float(row[1]),
            "match_reason": "API description matches your query",
            "source": "api_level",
        }
        for row in rows
        if float(row[1]) > settings.search_similarity_threshold
    ]


async def _search_endpoint_level(
    db: AsyncSession,
    query_embedding: list[float],
    query_text: str,
    domain: str | None,
    status: str | None,
    top_k: int,
) -> list[dict]:
    """Search at the endpoint level and bubble up to parent APIs."""
    similarity = (1 - APIEndpoint.embedding.cosine_distance(query_embedding)).label("similarity")

    stmt = (
        select(APIEndpoint, similarity, APICatalog)
        .join(APICatalog, APIEndpoint.api_id == APICatalog.id)
        .where(APIEndpoint.embedding.isnot(None))
    )

    if domain:
        stmt = stmt.where(APICatalog.domain == domain)
    if status:
        stmt = stmt.where(APICatalog.status == status)

    stmt = stmt.order_by(similarity.desc()).limit(top_k * 2)

    result = await db.execute(stmt)
    rows = result.all()

    # Group endpoints by parent API
    api_map: dict[UUID, dict] = {}
    for row in rows:
        endpoint, score, api = row
        score = float(score)
        if score <= settings.search_similarity_threshold:
            continue

        api_id = api.id
        if api_id not in api_map:
            # Load endpoints for this API
            ep_stmt = select(APIEndpoint).where(APIEndpoint.api_id == api_id)
            ep_result = await db.execute(ep_stmt)
            all_endpoints = list(ep_result.scalars().all())

            api_map[api_id] = {
                "api": api,
                "endpoints": all_endpoints,
                "matching_endpoints": [endpoint],
                "relevance_score": score,
                "match_reason": f"Endpoint {endpoint.method} {endpoint.path} matches your query",
                "source": "endpoint_level",
            }
        else:
            api_map[api_id]["matching_endpoints"].append(endpoint)
            api_map[api_id]["relevance_score"] = max(
                api_map[api_id]["relevance_score"], score
            )

    return list(api_map.values())


def _merge_results(
    api_results: list[dict],
    endpoint_results: list[dict],
    top_k: int,
) -> list[dict]:
    """Merge API-level and endpoint-level results, deduplicating by API ID."""
    seen_apis: dict[UUID, dict] = {}

    # API-level results get a slight boost since they matched at a higher level
    for r in api_results:
        api_id = r["api"].id
        r["relevance_score"] *= 1.1  # 10% boost for API-level match
        seen_apis[api_id] = r

    # Endpoint-level results
    for r in endpoint_results:
        api_id = r["api"].id
        if api_id in seen_apis:
            # Already found via API-level search — boost score
            existing = seen_apis[api_id]
            existing["relevance_score"] = max(
                existing["relevance_score"], r["relevance_score"]
            )
            existing["match_reason"] += f" | Also matched at endpoint level"
        else:
            seen_apis[api_id] = r

    # Sort by score and return top_k
    results = sorted(seen_apis.values(), key=lambda x: x["relevance_score"], reverse=True)
    return results[:top_k]


async def _get_annotations(db: AsyncSession, api_id: UUID) -> list[Annotation]:
    """Fetch all annotations for an API."""
    stmt = (
        select(Annotation)
        .where(Annotation.api_id == api_id)
        .order_by(Annotation.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


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
