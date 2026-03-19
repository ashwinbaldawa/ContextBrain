"""
Chat service — conversational API discovery powered by Claude.

Takes a developer's natural language question, searches the API catalog,
and uses Claude to synthesize a helpful, context-rich answer.
"""

import logging
import uuid

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.services.search import search_apis
from src.models import APICatalog

logger = logging.getLogger(__name__)
settings = get_settings()

# In-memory conversation store (replace with Redis/DB for production)
_conversations: dict[str, list[dict]] = {}


async def chat(
    db: AsyncSession,
    message: str,
    conversation_id: str | None = None,
) -> tuple[str, list[APICatalog], str]:
    """
    Process a chat message for API discovery.

    1. Search the API catalog based on the message
    2. Build context from search results (specs, annotations, etc.)
    3. Send to Claude with the context for a synthesized response

    Returns:
        Tuple of (response text, referenced APIs, conversation ID)
    """
    # Manage conversation
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
    if conversation_id not in _conversations:
        _conversations[conversation_id] = []

    # Search for relevant APIs
    search_results = await search_apis(db, message, top_k=5)

    # Build context document from search results
    context = _build_context(search_results)

    # Build conversation history
    history = _conversations[conversation_id]
    history.append({"role": "user", "content": message})

    # Call Claude
    response_text = await _call_claude(context, history)

    # Store assistant response in conversation
    history.append({"role": "assistant", "content": response_text})

    # Keep conversation history manageable
    if len(history) > 20:
        history[:] = history[-20:]

    # Extract referenced APIs
    referenced_apis = [r["api"] for r in search_results]

    return response_text, referenced_apis, conversation_id


async def _call_claude(context: str, conversation_history: list[dict]) -> str:
    """Call Claude with API context and conversation history."""
    if not settings.anthropic_api_key:
        return _fallback_response(context)

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        system_prompt = f"""You are APIBrain, an AI assistant that helps developers discover and understand internal APIs in a large healthcare organization.

You have access to the following API catalog information:

{context}

Your job is to:
1. Help developers find the right API(s) for their use case
2. Explain what each API does in plain business terms
3. Highlight relevant endpoints and their purpose
4. Surface annotations (gotchas, tips, workarounds) from other developers
5. Suggest which APIs to use together when a task requires multiple
6. Mention the API owner/team so the developer knows who to contact

Be specific and actionable. When you reference an API, always include:
- The API name and version
- The relevant endpoint(s) with method and path
- Any relevant annotations/warnings
- The owner team

If the query doesn't match any APIs in the catalog, say so honestly and suggest how to refine the search.

Keep responses concise and well-structured. Use the information from the catalog — don't make up APIs or endpoints that aren't in the context."""

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=system_prompt,
            messages=conversation_history,
        )

        return response.content[0].text.strip()

    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        return _fallback_response(context)


def _build_context(search_results: list[dict]) -> str:
    """Build a context document from search results for Claude."""
    if not search_results:
        return "No APIs found in the catalog matching this query."

    sections = []

    for i, result in enumerate(search_results, 1):
        api = result["api"]
        endpoints = result["endpoints"]
        annotations = result.get("annotations", [])

        section = f"""--- API #{i}: {api.name} (v{api.version}) ---
Domain: {api.domain or 'Not specified'}
Owner: {api.owner_team or 'Not specified'} ({api.owner_contact or 'No contact listed'})
Status: {api.status}
Auth: {api.auth_mechanism or 'Not specified'}
Base URL: {api.base_url or 'Not specified'}

Description: {api.business_description or api.description or 'No description'}

Endpoints:"""

        for ep in endpoints:
            section += f"""
  {ep.method} {ep.path}
    Summary: {ep.summary or 'No summary'}
    Business Description: {ep.business_description or 'Not enriched yet'}"""

        if annotations:
            section += "\n\nAnnotations (developer notes):"
            for ann in annotations:
                section += f"""
  ⚠️ [{ann.category.upper()}] "{ann.content}" — @{ann.author} ({ann.created_at.strftime('%Y-%m-%d')})"""

        section += f"\n\nRelevance Score: {result['relevance_score']:.3f}"
        sections.append(section)

    return "\n\n".join(sections)


def _fallback_response(context: str) -> str:
    """Generate a basic response when Claude is unavailable."""
    if "No APIs found" in context:
        return ("I couldn't find any APIs matching your query. "
                "Try rephrasing or using different keywords.")

    return f"Here's what I found in the API catalog:\n\n{context}\n\n(Note: AI-enhanced responses require an Anthropic API key. Set ANTHROPIC_API_KEY in your .env file.)"
