"""
Database initialization script.

Creates the database tables and installs the pgvector extension.
Run once on first setup: python scripts/init_db.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.database import engine, Base
from src.models import APICatalog, APIEndpoint, Annotation, UsageLog  # noqa: F401


async def init_database():
    """Create all tables and install pgvector extension."""
    async with engine.begin() as conn:
        # Install pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        print("✅ pgvector extension installed")

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created")

    # Verify
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        tables = [row[0] for row in result.fetchall()]
        print(f"\n📋 Tables in database: {', '.join(tables)}")

    await engine.dispose()
    print("\n🧠 APIBrain database initialized successfully!")


if __name__ == "__main__":
    asyncio.run(init_database())
