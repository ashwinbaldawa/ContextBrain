"""
Ingestion service — parses OpenAPI specs, enriches descriptions with AI,
generates embeddings, and stores everything in the database.
"""

import logging
from uuid import UUID

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models import APICatalog, APIEndpoint
from src.utils.openapi_parser import parse_openapi_spec, generate_api_summary
from src.services.embedding import generate_embedding, generate_embeddings_batch

logger = logging.getLogger(__name__)
settings = get_settings()


async def ingest_openapi_spec(
    db: AsyncSession,
    spec: dict,
    domain: str | None = None,
    owner_team: str | None = None,
    owner_contact: str | None = None,
    gateway_id: str | None = None,
) -> tuple[APICatalog, int]:
    """
    Ingest an OpenAPI spec into the database.

    1. Parse the spec into structured data
    2. Enrich descriptions using Claude
    3. Generate embeddings
    4. Store in PostgreSQL

    Returns:
        Tuple of (APICatalog record, endpoint count)
    """
    # Step 1: Parse
    parsed = parse_openapi_spec(spec)
    logger.info(f"Parsed API: {parsed['name']} with {len(parsed['endpoints'])} endpoints")

    # Step 2: Enrich with AI
    business_description = await _enrich_api_description(parsed)
    endpoint_descriptions = await _enrich_endpoint_descriptions(parsed)

    # Step 3: Generate embeddings
    api_summary = generate_api_summary(parsed)
    api_embed_text = f"{parsed['name']}. {business_description}. {api_summary}"
    api_embedding = await generate_embedding(api_embed_text)

    # Step 4: Store API
    api_record = APICatalog(
        name=parsed["name"],
        version=parsed["version"],
        domain=domain,
        owner_team=owner_team,
        owner_contact=owner_contact,
        description=parsed["description"],
        business_description=business_description,
        base_url=parsed["base_url"],
        auth_mechanism=parsed["auth_mechanism"],
        openapi_spec=spec,
        gateway_id=gateway_id,
        embedding=api_embedding,
    )
    db.add(api_record)
    await db.flush()  # Get the ID

    # Step 5: Store endpoints with embeddings
    endpoint_texts = []
    for i, ep in enumerate(parsed["endpoints"]):
        desc = endpoint_descriptions[i] if i < len(endpoint_descriptions) else ep["summary"]
        embed_text = f"{ep['method']} {ep['path']}. {desc}. {ep['summary']}"
        endpoint_texts.append(embed_text)

    endpoint_embeddings = await generate_embeddings_batch(endpoint_texts)

    for i, ep in enumerate(parsed["endpoints"]):
        desc = endpoint_descriptions[i] if i < len(endpoint_descriptions) else None
        endpoint_record = APIEndpoint(
            api_id=api_record.id,
            method=ep["method"],
            path=ep["path"],
            summary=ep["summary"],
            business_description=desc,
            parameters=ep["parameters"] if ep["parameters"] else None,
            request_schema=ep["request_schema"],
            response_schema=ep["response_schema"],
            embedding=endpoint_embeddings[i] if i < len(endpoint_embeddings) else None,
        )
        db.add(endpoint_record)

    await db.flush()
    logger.info(f"Stored API '{parsed['name']}' with {len(parsed['endpoints'])} endpoints")

    return api_record, len(parsed["endpoints"])


async def _enrich_api_description(parsed: dict) -> str:
    """Use Claude to generate a business-friendly description of the API."""
    if not settings.anthropic_api_key:
        logger.warning("No Anthropic API key — skipping AI enrichment")
        return parsed["description"] or f"API: {parsed['name']}"

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        summary = generate_api_summary(parsed)

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": f"""Given this API specification summary, write a clear 2-3 sentence 
business description that a developer could use to understand what this API does, 
when to use it, and what business problems it solves. 
Write in plain English, no technical jargon. Focus on the WHAT and WHEN, not the HOW.

API Spec:
{summary}

Respond with ONLY the description, no preamble.""",
                }
            ],
        )
        return response.content[0].text.strip()

    except Exception as e:
        logger.error(f"AI enrichment failed: {e}")
        return parsed["description"] or f"API: {parsed['name']}"


async def _enrich_endpoint_descriptions(parsed: dict) -> list[str]:
    """Use Claude to generate business-friendly descriptions for each endpoint."""
    if not settings.anthropic_api_key or not parsed["endpoints"]:
        return [ep["summary"] or f"{ep['method']} {ep['path']}" for ep in parsed["endpoints"]]

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        endpoints_text = "\n".join(
            f"- {ep['method']} {ep['path']}: {ep['summary']}"
            for ep in parsed["endpoints"]
        )

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": f"""For each API endpoint below, write a one-sentence business description 
explaining what it does in plain English. Focus on the business use case, not technical details.

API: {parsed['name']}
Endpoints:
{endpoints_text}

Respond with ONLY the descriptions, one per line, in the same order. No numbering, no bullets.""",
                }
            ],
        )

        descriptions = response.content[0].text.strip().split("\n")
        # Pad or trim to match endpoint count
        while len(descriptions) < len(parsed["endpoints"]):
            descriptions.append(parsed["endpoints"][len(descriptions)]["summary"])
        return descriptions[: len(parsed["endpoints"])]

    except Exception as e:
        logger.error(f"Endpoint enrichment failed: {e}")
        return [ep["summary"] or f"{ep['method']} {ep['path']}" for ep in parsed["endpoints"]]
