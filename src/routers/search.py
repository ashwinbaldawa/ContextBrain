"""Router for API search."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas import (
    SearchResponse, SearchResultItem, APIResponse,
    EndpointResponse, AnnotationResponse, APIListResponse, APIDetailResponse,
)
from src.services.search import search_apis, get_all_apis, get_api_by_id
from uuid import UUID

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Search & Browse"])


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    domain: str | None = Query(None, description="Filter by domain"),
    status: str | None = Query(None, description="Filter by status"),
    top_k: int = Query(5, ge=1, le=20, description="Number of results"),
    db: AsyncSession = Depends(get_db),
):
    """Semantic search across all APIs and endpoints."""
    results = await search_apis(db, q, domain=domain, status=status, top_k=top_k)

    items = []
    for r in results:
        api = r["api"]
        items.append(
            SearchResultItem(
                api=APIResponse.model_validate(api),
                endpoints=[EndpointResponse.model_validate(ep) for ep in r["endpoints"]],
                annotations=[AnnotationResponse.model_validate(a) for a in r.get("annotations", [])],
                relevance_score=r["relevance_score"],
                match_reason=r["match_reason"],
            )
        )

    return SearchResponse(query=q, results=items, total=len(items))


@router.get("/apis", response_model=APIListResponse)
async def list_apis(db: AsyncSession = Depends(get_db)):
    """List all APIs in the catalog."""
    apis = await get_all_apis(db)
    return APIListResponse(
        apis=[APIResponse.model_validate(a) for a in apis],
        total=len(apis),
    )


@router.get("/apis/{api_id}", response_model=APIDetailResponse)
async def get_api(api_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single API with full details, endpoints, and annotations."""
    from fastapi import HTTPException

    api = await get_api_by_id(db, api_id)
    if not api:
        raise HTTPException(status_code=404, detail="API not found")
    return APIDetailResponse.model_validate(api)
