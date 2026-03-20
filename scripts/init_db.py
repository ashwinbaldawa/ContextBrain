"""
Database initialization script.

Creates PostgreSQL tables and initializes ChromaDB collections.
Run once on first setup: python scripts/init_db.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.database import engine, Base
from src.models import APICatalog, APIEndpoint, Annotation, UsageLog  # noqa: F401


async def init_database():
    """Create PostgreSQL tables and initialize ChromaDB."""

    # --- PostgreSQL ---
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("✅ PostgreSQL tables created")

    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        tables = [row[0] for row in result.fetchall()]
        print(f"   Tables: {', '.join(tables)}")

    await engine.dispose()

    # --- ChromaDB ---
    from src.services.vectorstore import get_collection_stats
    stats = get_collection_stats()
    print(f"✅ ChromaDB collections initialized")
    print(f"   APIs: {stats['api_count']}, Endpoints: {stats['endpoint_count']}")

    print("\n🧠 ContextBrain database initialized successfully!")


if __name__ == "__main__":
    asyncio.run(init_database())
