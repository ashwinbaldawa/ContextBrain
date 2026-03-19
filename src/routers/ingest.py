"""Router for API spec ingestion."""

import logging
import yaml
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas import IngestRequest, IngestResponse
from src.services.ingestion import ingest_openapi_spec

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ingest", tags=["Ingestion"])


@router.post("", response_model=IngestResponse)
async def ingest_spec(
    request: IngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest an OpenAPI specification (JSON body)."""
    try:
        api_record, endpoint_count = await ingest_openapi_spec(
            db=db,
            spec=request.spec,
            domain=request.domain,
            owner_team=request.owner_team,
            owner_contact=request.owner_contact,
            gateway_id=request.gateway_id,
        )
        return IngestResponse(
            api_id=api_record.id,
            name=api_record.name,
            version=api_record.version,
            endpoints_count=endpoint_count,
            message=f"Successfully ingested '{api_record.name}' with {endpoint_count} endpoints",
        )
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to ingest spec: {str(e)}")


@router.post("/upload", response_model=IngestResponse)
async def ingest_spec_file(
    file: UploadFile = File(...),
    domain: str | None = None,
    owner_team: str | None = None,
    owner_contact: str | None = None,
    gateway_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Ingest an OpenAPI specification from a file upload (JSON or YAML)."""
    try:
        content = await file.read()
        text = content.decode("utf-8")

        # Parse as YAML (also handles JSON since JSON is valid YAML)
        spec = yaml.safe_load(text)

        if not isinstance(spec, dict):
            raise HTTPException(status_code=400, detail="Invalid spec: expected a JSON/YAML object")

        api_record, endpoint_count = await ingest_openapi_spec(
            db=db,
            spec=spec,
            domain=domain,
            owner_team=owner_team,
            owner_contact=owner_contact,
            gateway_id=gateway_id,
        )
        return IngestResponse(
            api_id=api_record.id,
            name=api_record.name,
            version=api_record.version,
            endpoints_count=endpoint_count,
            message=f"Successfully ingested '{api_record.name}' with {endpoint_count} endpoints",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File ingestion failed: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to ingest file: {str(e)}")
