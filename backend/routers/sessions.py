"""Sessions router — chat history management."""
from __future__ import annotations
import logging

from fastapi import APIRouter, Request, HTTPException, Query, status

from services.auth import require_auth, get_current_user
from models.database import (
    get_user_sessions, get_session_with_messages,
    delete_session, update_session_title, search_user_history,
    get_anonymous_sessions, search_anonymous_history,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """List chat sessions — user-owned if logged in, anonymous otherwise."""
    user = await get_current_user(request)
    if user:
        return await get_user_sessions(user["id"], page=page, limit=limit)
    # Anonymous: return recent sessions with no user_id
    return await get_anonymous_sessions(page=page, limit=limit)


@router.get("/search")
async def search_sessions(
    request: Request,
    q: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(20, ge=1, le=100),
):
    """Search across chat history."""
    user = await get_current_user(request)
    if user:
        results = await search_user_history(user["id"], q, limit=limit)
    else:
        results = await search_anonymous_history(q, limit=limit)
    return {"query": q, "results": results, "total": len(results)}


@router.get("/{session_id}")
async def get_session(request: Request, session_id: str):
    """Get full chat history for a specific session."""
    user = await get_current_user(request)
    user_id = user["id"] if user else None
    session = await get_session_with_messages(session_id, user_id=user_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.put("/{session_id}")
async def rename_session(request: Request, session_id: str, title: str = Query(..., min_length=1, max_length=200)):
    """Rename a chat session."""
    user = await require_auth(request)
    # Verify ownership
    session = await get_session_with_messages(session_id, user_id=user["id"])
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    await update_session_title(session_id, title)
    return {"id": session_id, "title": title}


@router.delete("/{session_id}")
async def remove_session(request: Request, session_id: str):
    """Delete a session and all its messages."""
    user = await require_auth(request)
    deleted = await delete_session(session_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return {"deleted": True, "id": session_id}


@router.get("/{session_id}/export")
async def export_session(request: Request, session_id: str):
    """Export a session as a structured JSON document."""
    user = await require_auth(request)
    session = await get_session_with_messages(session_id, user_id=user["id"])
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Format for export
    export_data = {
        "export_type": "nyaya_saathi_chat",
        "version": "3.0",
        "session": {
            "id": session["id"],
            "title": session["title"],
            "created_at": session["created_at"],
            "language": session["language"],
        },
        "messages": [
            {
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": msg.get("created_at", ""),
            }
            for msg in session["messages"]
        ],
        "message_count": len(session["messages"]),
    }
    return export_data
