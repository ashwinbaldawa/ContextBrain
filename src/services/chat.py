"""
Chat service — conversational API discovery powered by Google Gemini.

Takes a developer's natural language question, searches the API catalog
via ChromaDB, and uses Gemini to synthesize a helpful, context-rich answer.
"""

import logging
import uuid

import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.services.search import search_apis
from src.models import APICatalog

logger = logging.getLogger(__name__)
settings = get_settings()

# In-memory conversation store (replace with Redis/DB for production)
_conversations: dict[str, list[dict]] = {}


SYSTEM_PROMPT = """You are ContextBrain, an AI assistant that helps developers discover and understand internal APIs in a large healthcare organization.

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


async def chat(
    db: AsyncSession,
    message: str,
    conversation_id: str | None = None,
) -> tuple[str, list[APICatalog], str]:
    """
    Process a chat message for API discovery.

    1. Search the API catalog based on the message
    2. Build context from search results
    3. Send to Gemini with the context for a synthesized response

    Returns:
        Tuple of (response text, referenced APIs, conversation ID)
    """
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
    if conversation_id not in _conversations:
        _conversations[conversation_id] = []

    # Search for relevant APIs
    search_results = await search_apis(db, message, top_k=5)

    # Build context document
    context = _build_context(search_results)

    # Build conversation history
    history = _conversations[conversation_id]
    history.append({"role": "user", "content": message})

    # Call Gemini
    response_text = await _call_gemini(context, history)

    # Store response
    history.append({"role": "assistant", "content": response_text})
    if len(history) > 20:
        history[:] = history[-20:]

    referenced_apis = [r["api"] for r in search_results]
    return response_text, referenced_apis, conversation_id


async def _call_gemini(context: str, conversation_history: list[dict]) -> str:
    """Call Gemini with API context and conversation history."""
    if not settings.google_api_key:
        return _fallback_response(context)

    try:
        genai.configure(api_key=settings.google_api_key)
        model = genai.GenerativeModel(
            settings.gemini_llm_model,
            system_instruction=SYSTEM_PROMPT.format(context=context),
        )

        # Convert conversation history to Gemini format
        gemini_history = []
        for msg in conversation_history[:-1]:  # All except the last (current) message
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg["content"]]})

        chat_session = model.start_chat(history=gemini_history)

        # Send the latest message
        current_message = conversation_history[-1]["content"]
        response = chat_session.send_message(
            current_message,
            generation_config={"max_output_tokens": 1500, "temperature": 0.4},
        )

        return response.text.strip()

    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        return _fallback_response(context)


def _build_context(search_results: list[dict]) -> str:
    """Build a context document from search results for Gemini."""
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
    """Generate a basic response when Gemini is unavailable."""
    if "No APIs found" in context:
        return ("I couldn't find any APIs matching your query. "
                "Try rephrasing or using different keywords.")

    return (
        f"Here's what I found in the API catalog:\n\n{context}\n\n"
        "(Note: AI-enhanced responses require a Google API key. "
        "Set GOOGLE_API_KEY in your .env file.)"
    )
