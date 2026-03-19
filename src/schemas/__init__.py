"""Pydantic schemas for API catalog requests and responses."""

from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


# --- Annotation Schemas ---

class AnnotationCreate(BaseModel):
    api_id: UUID
    endpoint_id: UUID | None = None
    content: str = Field(..., min_length=1, max_length=2000)
    author: str = Field(..., min_length=1, max_length=255)
    category: str = Field(default="tip", pattern="^(gotcha|workaround|tip|correction|deprecation)$")


class AnnotationResponse(BaseModel):
    id: UUID
    api_id: UUID
    endpoint_id: UUID | None
    content: str
    author: str
    category: str
    verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Endpoint Schemas ---

class EndpointResponse(BaseModel):
    id: UUID
    method: str
    path: str
    summary: str | None
    business_description: str | None
    parameters: dict | None
    request_schema: dict | None
    response_schema: dict | None

    model_config = {"from_attributes": True}


# --- API Schemas ---

class APIResponse(BaseModel):
    id: UUID
    name: str
    version: str
    domain: str | None
    owner_team: str | None
    owner_contact: str | None
    status: str
    description: str | None
    business_description: str | None
    base_url: str | None
    auth_mechanism: str | None
    gateway_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class APIDetailResponse(APIResponse):
    endpoints: list[EndpointResponse] = []
    annotations: list[AnnotationResponse] = []


class APIListResponse(BaseModel):
    apis: list[APIResponse]
    total: int


# --- Ingestion Schemas ---

class IngestRequest(BaseModel):
    """Request to ingest an OpenAPI spec."""
    spec: dict = Field(..., description="OpenAPI/Swagger specification as JSON")
    domain: str | None = Field(None, description="Business domain (e.g., benefits, claims)")
    owner_team: str | None = Field(None, description="Team that owns this API")
    owner_contact: str | None = Field(None, description="Contact person for this API")
    gateway_id: str | None = Field(None, description="ID in the API gateway (e.g., AXWAY)")


class IngestResponse(BaseModel):
    api_id: UUID
    name: str
    version: str
    endpoints_count: int
    message: str


# --- Search Schemas ---

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    domain: str | None = None
    status: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResultItem(BaseModel):
    api: APIResponse
    endpoints: list[EndpointResponse]
    annotations: list[AnnotationResponse]
    relevance_score: float
    match_reason: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    total: int


# --- Chat Schemas ---

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    apis_referenced: list[APIResponse] = []
    conversation_id: str
