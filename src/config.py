"""Application configuration — loads from .env file."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://apibrain:apibrain@localhost:5432/apibrain"
    database_url_sync: str = "postgresql://apibrain:apibrain@localhost:5432/apibrain"

    # Anthropic
    anthropic_api_key: str = ""

    # Embedding
    embedding_model: str = "voyage-3"
    embedding_dimensions: int = 1024

    # Application
    app_env: str = "development"
    app_port: int = 8000
    log_level: str = "info"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Search
    search_top_k: int = 10
    search_similarity_threshold: float = 0.3

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
