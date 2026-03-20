"""
Ingestion service — parses OpenAPI specs, enriches descriptions with Gemini,
generates embeddings, and stores vectors in ChromaDB + relational data in PostgreSQL.
"""

import logging
from uuid import UUID

import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models import APICatalog, APIEndpoint
from src.utils.openapi_parser import parse_openapi_spec, generate_api_summary
from src.services.embedding import generate_embedding, generate_embeddings_batch
from src.services import vectorstore

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
    Ingest an OpenAPI spec into the system.

    1. Parse the spec into structured data
    2. Enrich descriptions using Gemini
    3. Store relational data in PostgreSQL
    4. Generate embeddings and store in ChromaDB

    Returns:
        Tuple of (APICatalog record, endpoint count)
    """
    # Step 1: Parse
    parsed = parse_openapi_spec(spec)
    logger.info(f"Parsed API: {parsed['name']} with {len(parsed['endpoints'])} endpoints")

    # Step 2: Enrich with Gemini
    business_description = await _enrich_api_description(parsed)
    endpoint_descriptions = await _enrich_endpoint_descriptions(parsed)

    # Step 3: Store relational data in PostgreSQL
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
    )
    db.add(api_record)
    await db.flush()  # Get the ID

    # Store endpoints in PostgreSQL
    endpoint_records = []
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
        )
        db.add(endpoint_record)
        endpoint_records.append(endpoint_record)

    await db.flush()

    # Step 4: Generate embeddings and store in ChromaDB
    api_summary = generate_api_summary(parsed)
    api_embed_text = f"{parsed['name']}. {business_description}. {api_summary}"
    api_embedding = generate_embedding(api_embed_text)

    vectorstore.upsert_api_embedding(
        api_id=str(api_record.id),
        embedding=api_embedding,
        document=api_embed_text,
        metadata={
            "name": parsed["name"],
            "version": parsed["version"],
            "domain": domain or "",
            "owner_team": owner_team or "",
            "status": "active",
        },
    )

    # Endpoint embeddings
    for i, (ep, record) in enumerate(zip(parsed["endpoints"], endpoint_records)):
        desc = endpoint_descriptions[i] if i < len(endpoint_descriptions) else ep["summary"]
        embed_text = f"{ep['method']} {ep['path']}. {desc}. API: {parsed['name']}"
        ep_embedding = generate_embedding(embed_text)

        vectorstore.upsert_endpoint_embedding(
            endpoint_id=str(record.id),
            api_id=str(api_record.id),
            embedding=ep_embedding,
            document=embed_text,
            metadata={
                "api_name": parsed["name"],
                "method": ep["method"],
                "path": ep["path"],
            },
        )

    logger.info(f"Stored '{parsed['name']}': {len(parsed['endpoints'])} endpoints in DB + ChromaDB")
    return api_record, len(parsed["endpoints"])


async def _enrich_api_description(parsed: dict) -> str:
    """Use Gemini to generate a business-friendly description of the API."""
    if not settings.google_api_key:
        logger.warning("No Google API key — skipping AI enrichment")
        return parsed["description"] or f"API: {parsed['name']}"

    try:
        genai.configure(api_key=settings.google_api_key)
        model = genai.GenerativeModel(settings.gemini_llm_model)
        summary = generate_api_summary(parsed)

        response = model.generate_content(
            f"""Given this API specification summary, write a clear 2-3 sentence 
business description that a developer could use to understand what this API does, 
when to use it, and what business problems it solves. 
Write in plain English, no technical jargon. Focus on the WHAT and WHEN, not the HOW.

API Spec:
{summary}

Respond with ONLY the description, no preamble.""",
            generation_config={"max_output_tokens": 300, "temperature": 0.3},
        )
        return response.text.strip()

    except Exception as e:
        logger.error(f"Gemini enrichment failed: {e}")
        return parsed["description"] or f"API: {parsed['name']}"


async def _enrich_endpoint_descriptions(parsed: dict) -> list[str]:
    """Use Gemini to generate business-friendly descriptions for each endpoint."""
    if not settings.google_api_key or not parsed["endpoints"]:
        return [ep["summary"] or f"{ep['method']} {ep['path']}" for ep in parsed["endpoints"]]

    try:
        genai.configure(api_key=settings.google_api_key)
        model = genai.GenerativeModel(settings.gemini_llm_model)

        endpoints_text = "\n".join(
            f"- {ep['method']} {ep['path']}: {ep['summary']}"
            for ep in parsed["endpoints"]
        )

        response = model.generate_content(
            f"""For each API endpoint below, write a one-sentence business description 
explaining what it does in plain English. Focus on the business use case, not technical details.

API: {parsed['name']}
Endpoints:
{endpoints_text}

Respond with ONLY the descriptions, one per line, in the same order. No numbering, no bullets.""",
            generation_config={"max_output_tokens": 1000, "temperature": 0.3},
        )

        descriptions = response.text.strip().split("\n")
        descriptions = [d.strip() for d in descriptions if d.strip()]
        while len(descriptions) < len(parsed["endpoints"]):
            descriptions.append(parsed["endpoints"][len(descriptions)]["summary"])
        return descriptions[: len(parsed["endpoints"])]

    except Exception as e:
        logger.error(f"Endpoint enrichment failed: {e}")
        return [ep["summary"] or f"{ep['method']} {ep['path']}" for ep in parsed["endpoints"]]
