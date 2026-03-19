"""Router for managing annotations on APIs and endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models import Annotation, APICatalog, APIEndpoint
from src.schemas import AnnotationCreate, AnnotationResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/annotations", tags=["Annotations"])


@router.post("", response_model=AnnotationResponse, status_code=201)
async def create_annotation(
    request: AnnotationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add an annotation to an API or specific endpoint."""
    # Verify API exists
    api = await db.get(APICatalog, request.api_id)
    if not api:
        raise HTTPException(status_code=404, detail="API not found")

    # Verify endpoint exists if specified
    if request.endpoint_id:
        endpoint = await db.get(APIEndpoint, request.endpoint_id)
        if not endpoint:
            raise HTTPException(status_code=404, detail="Endpoint not found")
        if endpoint.api_id != request.api_id:
            raise HTTPException(
                status_code=400, detail="Endpoint does not belong to the specified API"
            )

    annotation = Annotation(
        api_id=request.api_id,
        endpoint_id=request.endpoint_id,
        content=request.content,
        author=request.author,
        category=request.category,
    )
    db.add(annotation)
    await db.flush()
    await db.refresh(annotation)

    logger.info(f"Annotation added to API {api.name} by {request.author}")
    return AnnotationResponse.model_validate(annotation)


@router.get("/{target_id}", response_model=list[AnnotationResponse])
async def get_annotations(
    target_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all annotations for an API or endpoint."""
    # Check if it's an API ID or endpoint ID
    stmt = select(Annotation).where(
        (Annotation.api_id == target_id) | (Annotation.endpoint_id == target_id)
    ).order_by(Annotation.created_at.desc())

    result = await db.execute(stmt)
    annotations = list(result.scalars().all())

    return [AnnotationResponse.model_validate(a) for a in annotations]


@router.delete("/{annotation_id}", status_code=204)
async def delete_annotation(
    annotation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete an annotation."""
    annotation = await db.get(Annotation, annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    await db.delete(annotation)
    logger.info(f"Annotation {annotation_id} deleted")
