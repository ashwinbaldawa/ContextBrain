"""SQLAlchemy models for the API catalog, endpoints, and usage logs."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Enum as SAEnum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from src.database import Base
from src.config import get_settings

settings = get_settings()


class APICatalog(Base):
    """Represents a registered API in the catalog."""

    __tablename__ = "api_catalog"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    domain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    owner_team: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        SAEnum("active", "deprecated", "sunset", name="api_status"),
        default="active",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    auth_mechanism: Mapped[str | None] = mapped_column(String(100), nullable=True)
    openapi_spec: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    gateway_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding = mapped_column(Vector(settings.embedding_dimensions), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    endpoints: Mapped[list["APIEndpoint"]] = relationship(
        back_populates="api", cascade="all, delete-orphan"
    )
    annotations: Mapped[list["Annotation"]] = relationship(
        back_populates="api",
        foreign_keys="Annotation.api_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<APICatalog {self.name} v{self.version}>"


class APIEndpoint(Base):
    """Represents a single endpoint within an API."""

    __tablename__ = "api_endpoints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    api_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_catalog.id", ondelete="CASCADE")
    )
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    parameters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    embedding = mapped_column(Vector(settings.embedding_dimensions), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    api: Mapped["APICatalog"] = relationship(back_populates="endpoints")

    __table_args__ = (
        Index("ix_endpoint_api_method_path", "api_id", "method", "path"),
    )

    def __repr__(self) -> str:
        return f"<APIEndpoint {self.method} {self.path}>"


class Annotation(Base):
    """Developer-contributed notes attached to APIs or endpoints."""

    __tablename__ = "annotations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    api_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_catalog.id", ondelete="CASCADE")
    )
    endpoint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_endpoints.id", ondelete="CASCADE"),
        nullable=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(
        SAEnum("gotcha", "workaround", "tip", "correction", "deprecation", name="annotation_category"),
        default="tip",
    )
    verified: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    api: Mapped["APICatalog"] = relationship(
        back_populates="annotations", foreign_keys=[api_id]
    )

    def __repr__(self) -> str:
        return f"<Annotation by {self.author}: {self.content[:50]}>"


class UsageLog(Base):
    """Tracks developer interactions for analytics and feedback."""

    __tablename__ = "usage_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    selected_api_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False, default="search")
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
