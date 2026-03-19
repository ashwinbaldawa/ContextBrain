"""
Seed script — loads sample healthcare API specs into the database
along with realistic annotations for demo purposes.

Run after init_db.py: python scripts/seed_sample_apis.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from src.database import async_session, engine
from src.models import APICatalog, Annotation
from src.services.ingestion import ingest_openapi_spec

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_specs")

# Sample APIs with metadata
SAMPLES = [
    {
        "file": "member_eligibility_api.json",
        "domain": "benefits",
        "owner_team": "Benefits Platform Team",
        "owner_contact": "jane.doe@example.com",
        "gateway_id": "AXWAY-BEN-001",
    },
    {
        "file": "claims_processing_api.json",
        "domain": "claims",
        "owner_team": "Claims Engine Team",
        "owner_contact": "bob.smith@example.com",
        "gateway_id": "AXWAY-CLM-001",
    },
    {
        "file": "provider_network_api.json",
        "domain": "provider",
        "owner_team": "Provider Data Team",
        "owner_contact": "carol.jones@example.com",
        "gateway_id": "AXWAY-PRV-001",
    },
    {
        "file": "prior_authorization_api.json",
        "domain": "utilization_management",
        "owner_team": "UM Platform Team",
        "owner_contact": "dave.wilson@example.com",
        "gateway_id": "AXWAY-UM-001",
    },
]

# Realistic annotations to seed
ANNOTATIONS = {
    "Member Eligibility API": [
        {
            "content": "Dental and vision have separate endpoints — this API only covers medical and behavioral health benefits.",
            "author": "dev_smith",
            "category": "gotcha",
        },
        {
            "content": "Returns empty response for dependent-only plans. Must pass the subscriber's member ID with a dependent relationship indicator.",
            "author": "dev_patel",
            "category": "gotcha",
        },
        {
            "content": "Batch endpoint is rate-limited to 10 requests/minute per client. For large cohorts, add a delay between batches.",
            "author": "dev_jones",
            "category": "tip",
        },
    ],
    "Claims Processing API": [
        {
            "content": "The status field uses lowercase values but the spec shows mixed case. Always compare case-insensitively.",
            "author": "dev_chen",
            "category": "correction",
        },
        {
            "content": "OAuth token endpoint requires client_credentials grant, NOT authorization_code. The spec doesn't make this clear.",
            "author": "dev_smith",
            "category": "gotcha",
        },
        {
            "content": "For claims older than 18 months, use the /claims/archive endpoint instead (not documented in the main spec).",
            "author": "dev_kumar",
            "category": "workaround",
        },
    ],
    "Provider Network API": [
        {
            "content": "The zipCode search uses a centroid-based radius, not driving distance. Results at the edge of the radius may be further by road.",
            "author": "dev_johnson",
            "category": "tip",
        },
        {
            "content": "acceptingNewPatients data is updated weekly on Sundays. Don't rely on it for real-time availability.",
            "author": "dev_patel",
            "category": "gotcha",
        },
    ],
    "Prior Authorization API": [
        {
            "content": "Always call the eligibility API first to confirm active coverage before submitting a prior auth. The prior auth API assumes active coverage and returns a misleading success for inactive members.",
            "author": "dev_jones",
            "category": "gotcha",
        },
        {
            "content": "The auto-approval engine runs only during business hours (8am-6pm ET). Submissions outside this window get queued for next business day.",
            "author": "dev_wilson",
            "category": "tip",
        },
        {
            "content": "v2.2 had a bug where urgent requests were routed as routine. Fixed in v2.3 but some clients still reference the old version.",
            "author": "dev_chen",
            "category": "deprecation",
        },
    ],
}


async def seed():
    """Load sample APIs and annotations."""
    async with async_session() as db:
        # Check if already seeded
        result = await db.execute(select(APICatalog).limit(1))
        if result.scalar_one_or_none():
            print("⚠️  Database already has data. Skipping seed.")
            print("   To re-seed, drop the tables first: python scripts/init_db.py")
            return

        # Ingest each sample API
        api_name_to_id = {}
        for sample in SAMPLES:
            filepath = os.path.join(SAMPLE_DIR, sample["file"])
            if not os.path.exists(filepath):
                print(f"⚠️  Sample file not found: {filepath}")
                continue

            with open(filepath) as f:
                spec = json.load(f)

            print(f"📥 Ingesting {sample['file']}...")
            api_record, ep_count = await ingest_openapi_spec(
                db=db,
                spec=spec,
                domain=sample["domain"],
                owner_team=sample["owner_team"],
                owner_contact=sample["owner_contact"],
                gateway_id=sample["gateway_id"],
            )
            api_name_to_id[api_record.name] = api_record.id
            print(f"   ✅ {api_record.name} — {ep_count} endpoints")

        # Add annotations
        print("\n📝 Adding annotations...")
        for api_name, notes in ANNOTATIONS.items():
            api_id = api_name_to_id.get(api_name)
            if not api_id:
                continue

            for note in notes:
                annotation = Annotation(
                    api_id=api_id,
                    content=note["content"],
                    author=note["author"],
                    category=note["category"],
                )
                db.add(annotation)
            print(f"   ✅ {len(notes)} annotations for {api_name}")

        await db.commit()

    await engine.dispose()
    print("\n🧠 APIBrain seeded successfully!")
    print(f"   APIs: {len(api_name_to_id)}")
    print(f"   Annotations: {sum(len(v) for v in ANNOTATIONS.values())}")


if __name__ == "__main__":
    asyncio.run(seed())
