"""Chat router — SSE streaming endpoint for legal Q&A."""
from __future__ import annotations
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from models.schemas import ChatRequest, StreamChunk
from services.reasoning import process_chat
from services.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
async def chat(request: Request, chat_request: ChatRequest):
    """
    Process a legal question and stream the response.
    Supports both debate and simple modes via request.mode.
    Uses Server-Sent Events (SSE) for real-time streaming.

    Auth: Optional — anonymous users get ephemeral sessions,
    authenticated users get persistent history.
    """
    # Extract user if authenticated (None for anonymous)
    user = await get_current_user(request)
    user_id = user["id"] if user else None

    async def event_stream():
        async for chunk in process_chat(chat_request, user_id=user_id):
            data = json.dumps(chunk.model_dump(), ensure_ascii=False)
            yield f"data: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/simple")
async def chat_simple(request: Request, chat_request: ChatRequest):
    """
    Non-streaming version — returns complete response at once.
    Forces simple mode regardless of request.mode.
    """
    user = await get_current_user(request)
    user_id = user["id"] if user else None

    chat_request.mode = "simple"
    full_response = {}
    async for chunk in process_chat(chat_request, user_id=user_id):
        if chunk.type == "response":
            full_response.setdefault("text", "")
            full_response["text"] += chunk.data.get("text", "")
        elif chunk.type == "sources":
            full_response["sources"] = chunk.data.get("sources", [])
            full_response["confidence"] = chunk.data.get("confidence", 0)
            full_response["language"] = chunk.data.get("language", "en")
            full_response["urgency"] = chunk.data.get("urgency", {})
            full_response["grounding"] = chunk.data.get("grounding", {})
            full_response["mode"] = chunk.data.get("mode", "simple")
            full_response["pipeline_latency_ms"] = chunk.data.get("pipeline_latency_ms", 0)
        elif chunk.type == "urgency":
            full_response["urgency_alert"] = chunk.data
        elif chunk.type == "error":
            full_response["error"] = chunk.data.get("message", "Unknown error")
        elif chunk.type == "done":
            full_response["session_id"] = chunk.data.get("session_id", "")
        elif chunk.type == "query_analysis":
            full_response["query_analysis"] = chunk.data
        elif chunk.type == "debate_complete":
            full_response["debate"] = chunk.data

    return full_response
