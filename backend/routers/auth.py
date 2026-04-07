"""Auth router — signup, login, refresh, profile."""
from __future__ import annotations
import logging

from fastapi import APIRouter, Request, HTTPException, status

from models.schemas import UserCreate, UserLogin, UserUpdate, TokenResponse, RefreshRequest, UserProfile
from services.auth import (
    register_user, authenticate_user, create_access_token,
    create_refresh_token, hash_token, decode_token, require_auth,
)
from models.database import store_refresh_token, validate_refresh_token, revoke_refresh_token, revoke_user_tokens, update_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: UserCreate):
    """Register a new user and return tokens."""
    try:
        user = await register_user(body.email, body.password, body.name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    access_token, expires_in = create_access_token(user["id"], user["email"])
    refresh_token, refresh_expires = create_refresh_token(user["id"])

    # Store refresh token hash
    await store_refresh_token(hash_token(refresh_token), user["id"], refresh_expires)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=UserProfile(
            id=user["id"],
            email=user["email"],
            name=user.get("name", body.name),
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin):
    """Authenticate and return tokens."""
    user = await authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token, expires_in = create_access_token(user["id"], user["email"])
    refresh_token, refresh_expires = create_refresh_token(user["id"])

    await store_refresh_token(hash_token(refresh_token), user["id"], refresh_expires)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=UserProfile(
            id=user["id"],
            email=user["email"],
            name=user.get("name", ""),
            preferred_language=user.get("preferred_language", "en"),
            created_at=user.get("created_at", ""),
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    """Refresh an access token using a valid refresh token."""
    # Decode the refresh token
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Validate against database
    token_hash = hash_token(body.refresh_token)
    stored = await validate_refresh_token(token_hash)
    if not stored:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired or revoked")

    user_id = stored["user_id"]

    # Revoke old token and issue new pair
    await revoke_refresh_token(token_hash)

    from models.database import get_user_by_id
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    access_token, expires_in = create_access_token(user["id"], user["email"])
    new_refresh, refresh_expires = create_refresh_token(user["id"])
    await store_refresh_token(hash_token(new_refresh), user["id"], refresh_expires)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=expires_in,
        user=UserProfile(**user),
    )


@router.get("/me", response_model=UserProfile)
async def get_me(request: Request):
    """Get current user profile."""
    user = await require_auth(request)
    return UserProfile(**user)


@router.put("/me", response_model=UserProfile)
async def update_me(request: Request, body: UserUpdate):
    """Update current user profile."""
    user = await require_auth(request)
    await update_user(user["id"], name=body.name, lang=body.preferred_language)

    # Fetch updated user
    from models.database import get_user_by_id
    updated = await get_user_by_id(user["id"])
    return UserProfile(**updated)


@router.post("/logout")
async def logout(request: Request):
    """Revoke all refresh tokens for the current user."""
    user = await require_auth(request)
    await revoke_user_tokens(user["id"])
    return {"message": "Logged out successfully"}
