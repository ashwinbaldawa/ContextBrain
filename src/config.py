"""Application configuration — loads from .env file."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database (relational)
    database_url: str = "postgresql+asyncpg://contextbrain:contextbrain@localhost:5432/contextbrain"
    database_url_sync: str = "postgresql://contextbrain:contextbrain@localhost:5432/contextbrain"

    # Google Gemini
    google_api_key: str = ""
    gemini_llm_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "text-embedding-004"

    # ChromaDB
    chroma_mode: str = "local"  # "local" or "http"
    chroma_persist_dir: str = "./chroma_data"
    chroma_host: str = "localhost"
    chroma_port: int = 8100
    chroma_collection_name: str = "contextbrain_apis"

    # Application
    app_env: str = "development"
    app_port: int = 8000
    log_level: str = "info"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Search
    search_top_k: int = 10

    # Future: Vertex AI
    gcp_project_id: str = ""
    gcp_location: str = "us-central1"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
