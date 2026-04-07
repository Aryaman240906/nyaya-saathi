"""Bookmarks router — save and manage legal section bookmarks."""
from __future__ import annotations
import logging

from fastapi import APIRouter, Request, HTTPException, status

from models.schemas import BookmarkItem, BookmarkResponse
from services.auth import require_auth
from models.database import add_bookmark, get_bookmarks, delete_bookmark

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])


@router.post("", response_model=BookmarkResponse, status_code=status.HTTP_201_CREATED)
async def create_bookmark(request: Request, body: BookmarkItem):
    """Bookmark a legal section."""
    user = await require_auth(request)
    bookmark_id = await add_bookmark(
        user_id=user["id"],
        section_id=body.section_id,
        act=body.act,
        section_number=body.section_number,
        title=body.title,
        note=body.note,
    )
    return BookmarkResponse(
        id=bookmark_id,
        section_id=body.section_id,
        act=body.act,
        section_number=body.section_number,
        title=body.title,
        note=body.note,
    )


@router.get("")
async def list_bookmarks(request: Request):
    """List all bookmarks for the current user."""
    user = await require_auth(request)
    bookmarks = await get_bookmarks(user["id"])
    return {"bookmarks": bookmarks, "total": len(bookmarks)}


@router.delete("/{bookmark_id}")
async def remove_bookmark(request: Request, bookmark_id: str):
    """Delete a bookmark."""
    user = await require_auth(request)
    deleted = await delete_bookmark(bookmark_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")
    return {"deleted": True, "id": bookmark_id}
