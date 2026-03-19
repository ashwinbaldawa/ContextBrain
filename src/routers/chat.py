"""Router for conversational API discovery."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas import ChatRequest, ChatResponse, APIResponse
from src.services.chat import chat

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Conversational API discovery.

    Send a natural language message and get an AI-powered response
    that helps you find and understand the right APIs for your use case.
    Supports multi-turn conversations via conversation_id.
    """
    response_text, referenced_apis, conversation_id = await chat(
        db=db,
        message=request.message,
        conversation_id=request.conversation_id,
    )

    return ChatResponse(
        response=response_text,
        apis_referenced=[APIResponse.model_validate(api) for api in referenced_apis],
        conversation_id=conversation_id,
    )
