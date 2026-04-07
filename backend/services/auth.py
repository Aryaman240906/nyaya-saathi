"""
Authentication Service — JWT + bcrypt.

Provides:
- Password hashing with bcrypt (via passlib)
- JWT access token generation/validation (30min)
- JWT refresh token generation/validation (7 days)
- User extraction from Authorization header
"""
from __future__ import annotations
import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from fastapi import Request, HTTPException, status

import config
from models import database as db

logger = logging.getLogger(__name__)

# ── Password Hashing (direct bcrypt — passlib is incompatible with bcrypt 5.x) ─
import bcrypt as _bcrypt


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    # Truncate to 72 bytes (bcrypt limit)
    pwd_bytes = password.encode("utf-8")[:72]
    salt = _bcrypt.gensalt(rounds=12)
    return _bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return _bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


# ── JWT Tokens ─────────────────────────────────────────────────────

def create_access_token(user_id: str, email: str) -> tuple[str, int]:
    """Create a JWT access token. Returns (token, expires_in_seconds)."""
    expires_delta = timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "type": "access",
    }
    token = jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)
    return token, int(expires_delta.total_seconds())


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Create a refresh token. Returns (token, expires_at_iso)."""
    expires_delta = timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)
    return token, expire.isoformat()


def hash_token(token: str) -> str:
    """Hash a token for database storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns payload or None."""
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        return payload
    except JWTError as e:
        logger.debug("JWT decode failed: %s", e)
        return None


# ── User Authentication ────────────────────────────────────────────

async def authenticate_user(email: str, password: str) -> dict | None:
    """Authenticate user with email + password. Returns user dict or None."""
    user = await db.get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


async def register_user(email: str, password: str, name: str) -> dict:
    """Register a new user. Raises ValueError if email exists."""
    if await db.user_exists(email):
        raise ValueError("Email already registered")

    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)
    user = await db.create_user(user_id, email, password_hash, name)
    return user


# ── Request User Extraction ────────────────────────────────────────

async def get_current_user(request: Request) -> dict | None:
    """
    Extract current user from request.
    Returns user dict or None (for anonymous access).
    Does NOT raise — call require_auth() for protected routes.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    user = await db.get_user_by_id(user_id)
    return user


async def require_auth(request: Request) -> dict:
    """
    Extract current user from request. Raises 401 if not authenticated.
    Use as dependency for protected routes.
    """
    user = await get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please login first.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
