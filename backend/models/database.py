"""
SQLite database layer with user auth, sessions, bookmarks.

Uses async connection pool with WAL mode. Handles schema
migrations gracefully for existing databases.
"""
from __future__ import annotations
import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from models.db_pool import init_pool, db_session

logger = logging.getLogger(__name__)

DB_PATH: Path | None = None


# ── Schema ──────────────────────────────────────────────────────────


# ── Base table creation (no indexes that reference migration columns) ──

_TABLES_SQL = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    preferred_language TEXT DEFAULT 'en',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Sessions (base — user_id/title added via migration for existing DBs)
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    language TEXT DEFAULT 'en',
    metadata TEXT DEFAULT '{}'
);

-- Messages
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- Bookmarks
CREATE TABLE IF NOT EXISTS bookmarks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    section_id TEXT NOT NULL,
    act TEXT DEFAULT '',
    section_number TEXT DEFAULT '',
    title TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Refresh tokens
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

# ── Migrations for existing databases ───────────────────────────────

_MIGRATIONS = [
    ("sessions", "user_id", "ALTER TABLE sessions ADD COLUMN user_id TEXT"),
    ("sessions", "title", "ALTER TABLE sessions ADD COLUMN title TEXT DEFAULT ''"),
]

# ── Indexes (created AFTER migrations so columns exist) ─────────────

_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_bookmarks_user ON bookmarks(user_id, created_at)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_bookmarks_unique ON bookmarks(user_id, section_id)",
    "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash)",
]


async def init_db(db_path: Path):
    """Initialize the database with schema, run migrations, then create indexes."""
    global DB_PATH
    DB_PATH = db_path

    # Initialize connection pool
    await init_pool(db_path)

    async with db_session() as db:
        # 1. Create base tables (without indexes on migration columns)
        await db.executescript(_TABLES_SQL)

        # 2. Run migrations for existing databases
        for table, column, sql in _MIGRATIONS:
            try:
                cursor = await db.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in await cursor.fetchall()]
                if column not in columns:
                    await db.execute(sql)
                    logger.info("Migration: added %s.%s", table, column)
            except Exception as e:
                logger.debug("Migration skip (%s.%s): %s", table, column, e)

        # 3. Create indexes (after migrations added columns)
        for idx_sql in _INDEXES_SQL:
            try:
                await db.execute(idx_sql)
            except Exception as e:
                logger.debug("Index skip: %s", e)

    logger.info("✓ Database schema initialized")


# ── User Operations ─────────────────────────────────────────────────

async def create_user(user_id: str, email: str, password_hash: str, name: str) -> dict:
    """Create a new user."""
    now = datetime.now(timezone.utc).isoformat()
    async with db_session() as db:
        await db.execute(
            "INSERT INTO users (id, email, password_hash, name, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, email.lower().strip(), password_hash, name, now, now),
        )
    return {"id": user_id, "email": email, "name": name}


async def get_user_by_email(email: str) -> dict | None:
    """Find a user by email."""
    async with db_session() as db:
        cursor = await db.execute(
            "SELECT id, email, password_hash, name, preferred_language, created_at "
            "FROM users WHERE email = ?",
            (email.lower().strip(),),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0], "email": row[1], "password_hash": row[2],
            "name": row[3], "preferred_language": row[4], "created_at": row[5],
        }


async def get_user_by_id(user_id: str) -> dict | None:
    """Find a user by ID."""
    async with db_session() as db:
        cursor = await db.execute(
            "SELECT id, email, name, preferred_language, created_at FROM users WHERE id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0], "email": row[1], "name": row[2],
            "preferred_language": row[3], "created_at": row[4],
        }


async def update_user(user_id: str, name: str | None = None, lang: str | None = None):
    """Update user profile fields."""
    now = datetime.now(timezone.utc).isoformat()
    async with db_session() as db:
        if name is not None:
            await db.execute("UPDATE users SET name = ?, updated_at = ? WHERE id = ?", (name, now, user_id))
        if lang is not None:
            await db.execute("UPDATE users SET preferred_language = ?, updated_at = ? WHERE id = ?", (lang, now, user_id))


async def user_exists(email: str) -> bool:
    """Check if an email is already registered."""
    async with db_session() as db:
        cursor = await db.execute("SELECT 1 FROM users WHERE email = ?", (email.lower().strip(),))
        return await cursor.fetchone() is not None


# ── Refresh Token Operations ────────────────────────────────────────

async def store_refresh_token(token_hash: str, user_id: str, expires_at: str):
    """Store a refresh token hash."""
    now = datetime.now(timezone.utc).isoformat()
    async with db_session() as db:
        await db.execute(
            "INSERT INTO refresh_tokens (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (token_hash, user_id, expires_at, now),
        )


async def validate_refresh_token(token_hash: str) -> dict | None:
    """Validate a refresh token and return user_id if valid."""
    now = datetime.now(timezone.utc).isoformat()
    async with db_session() as db:
        cursor = await db.execute(
            "SELECT user_id, expires_at FROM refresh_tokens "
            "WHERE token_hash = ? AND revoked = 0 AND expires_at > ?",
            (token_hash, now),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {"user_id": row[0], "expires_at": row[1]}


async def revoke_refresh_token(token_hash: str):
    """Revoke a refresh token."""
    async with db_session() as db:
        await db.execute("UPDATE refresh_tokens SET revoked = 1 WHERE token_hash = ?", (token_hash,))


async def revoke_user_tokens(user_id: str):
    """Revoke all refresh tokens for a user."""
    async with db_session() as db:
        await db.execute("UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ?", (user_id,))


async def cleanup_expired_tokens():
    """Remove expired refresh tokens."""
    now = datetime.now(timezone.utc).isoformat()
    async with db_session() as db:
        await db.execute("DELETE FROM refresh_tokens WHERE expires_at < ? OR revoked = 1", (now,))


# ── Session Operations ──────────────────────────────────────────────

async def create_session(user_id: str | None = None, language: str = "en") -> str:
    """Create a new conversation session."""
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async with db_session() as db:
        await db.execute(
            "INSERT INTO sessions (id, user_id, created_at, updated_at, language) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, now, now, language),
        )
    return session_id


async def session_exists(session_id: str) -> bool:
    """Check if a session exists."""
    async with db_session() as db:
        cursor = await db.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,))
        return await cursor.fetchone() is not None


async def get_user_sessions(user_id: str, page: int = 1, limit: int = 20) -> dict:
    """Get paginated list of user's sessions with last message preview."""
    offset = (page - 1) * limit
    async with db_session() as db:
        # Count total
        cursor = await db.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,)
        )
        total = (await cursor.fetchone())[0]

        # Get sessions with last message
        cursor = await db.execute("""
            SELECT s.id, s.title, s.created_at, s.updated_at, s.language,
                   (SELECT content FROM messages WHERE session_id = s.id ORDER BY created_at DESC LIMIT 1) as last_message,
                   (SELECT COUNT(*) FROM messages WHERE session_id = s.id) as message_count
            FROM sessions s
            WHERE s.user_id = ?
            ORDER BY s.updated_at DESC
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset))

        sessions = []
        for row in await cursor.fetchall():
            sessions.append({
                "id": row[0],
                "title": row[1] or "Untitled",
                "created_at": row[2],
                "updated_at": row[3],
                "language": row[4],
                "last_message_preview": (row[5] or "")[:100],
                "message_count": row[6],
            })

        return {
            "sessions": sessions,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if limit > 0 else 0,
        }


async def get_session_with_messages(session_id: str, user_id: str | None = None) -> dict | None:
    """Get a session with all its messages. Enforces ownership if user_id provided."""
    async with db_session() as db:
        # Verify ownership
        if user_id:
            cursor = await db.execute(
                "SELECT id, title, created_at, language FROM sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            )
        else:
            # Anonymous: allow fetching any session with null user_id, or any session by ID
            cursor = await db.execute(
                "SELECT id, title, created_at, language FROM sessions WHERE id = ? AND (user_id IS NULL OR user_id = '')",
                (session_id,),
            )
        session_row = await cursor.fetchone()
        if not session_row:
            return None

        # Get messages
        cursor = await db.execute(
            "SELECT role, content, metadata, created_at FROM messages "
            "WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        )
        messages = []
        for row in await cursor.fetchall():
            messages.append({
                "role": row[0],
                "content": row[1],
                "metadata": json.loads(row[2]) if row[2] else {},
                "created_at": row[3],
            })

        return {
            "id": session_row[0],
            "title": session_row[1] or "Untitled",
            "created_at": session_row[2],
            "language": session_row[3],
            "messages": messages,
        }


async def delete_session(session_id: str, user_id: str) -> bool:
    """Delete a session and its messages (cascade). Returns True if deleted."""
    async with db_session() as db:
        cursor = await db.execute(
            "DELETE FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        return cursor.rowcount > 0


async def update_session_title(session_id: str, title: str):
    """Update session title."""
    now = datetime.now(timezone.utc).isoformat()
    async with db_session() as db:
        await db.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, session_id),
        )


async def search_user_history(user_id: str, query: str, limit: int = 20) -> list[dict]:
    """Full-text search across user's messages."""
    async with db_session() as db:
        cursor = await db.execute("""
            SELECT m.session_id, s.title, m.role, m.content, m.created_at
            FROM messages m
            JOIN sessions s ON m.session_id = s.id
            WHERE s.user_id = ? AND m.content LIKE ?
            ORDER BY m.created_at DESC
            LIMIT ?
        """, (user_id, f"%{query}%", limit))

        results = []
        for row in await cursor.fetchall():
            results.append({
                "session_id": row[0],
                "session_title": row[1] or "Untitled",
                "role": row[2],
                "content_preview": row[3][:200],
                "created_at": row[4],
            })
        return results


async def get_anonymous_sessions(page: int = 1, limit: int = 20) -> dict:
    """Get recent anonymous sessions (no user_id)."""
    offset = (page - 1) * limit
    async with db_session() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id IS NULL OR user_id = ''"
        )
        total = (await cursor.fetchone())[0]

        cursor = await db.execute("""
            SELECT s.id, s.title, s.created_at, s.updated_at, s.language,
                   (SELECT content FROM messages WHERE session_id = s.id ORDER BY created_at DESC LIMIT 1) as last_message,
                   (SELECT COUNT(*) FROM messages WHERE session_id = s.id) as message_count
            FROM sessions s
            WHERE s.user_id IS NULL OR s.user_id = ''
            ORDER BY s.updated_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        sessions = []
        for row in await cursor.fetchall():
            sessions.append({
                "id": row[0],
                "title": row[1] or "Untitled",
                "created_at": row[2],
                "updated_at": row[3],
                "language": row[4],
                "last_message_preview": (row[5] or "")[:100],
                "message_count": row[6],
            })

        return {
            "sessions": sessions,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if limit > 0 else 0,
        }


async def search_anonymous_history(query: str, limit: int = 20) -> list[dict]:
    """Search across anonymous sessions."""
    async with db_session() as db:
        cursor = await db.execute("""
            SELECT m.session_id, s.title, m.role, m.content, m.created_at
            FROM messages m
            JOIN sessions s ON m.session_id = s.id
            WHERE (s.user_id IS NULL OR s.user_id = '') AND m.content LIKE ?
            ORDER BY m.created_at DESC
            LIMIT ?
        """, (f"%{query}%", limit))

        results = []
        for row in await cursor.fetchall():
            results.append({
                "session_id": row[0],
                "session_title": row[1] or "Untitled",
                "role": row[2],
                "content_preview": row[3][:200],
                "created_at": row[4],
            })
        return results


# ── Message Operations ──────────────────────────────────────────────

async def add_message(session_id: str, role: str, content: str, metadata: dict | None = None):
    """Add a message to a session."""
    now = datetime.now(timezone.utc).isoformat()
    meta_str = json.dumps(metadata or {})
    async with db_session() as db:
        await db.execute(
            "INSERT INTO messages (session_id, role, content, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, meta_str, now),
        )
        await db.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )


async def get_history(session_id: str, limit: int = 10) -> list[dict]:
    """Get recent messages for a session."""
    async with db_session() as db:
        cursor = await db.execute(
            "SELECT role, content, metadata FROM messages WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
            (session_id, limit),
        )
        rows = await cursor.fetchall()
        return [
            {
                "role": row[0],
                "content": row[1],
                "metadata": json.loads(row[2]) if row[2] else {},
            }
            for row in reversed(rows)
        ]


# ── Bookmark Operations ────────────────────────────────────────────

async def add_bookmark(user_id: str, section_id: str, act: str = "",
                       section_number: str = "", title: str = "", note: str = "") -> str:
    """Add a bookmark. Returns bookmark ID."""
    bookmark_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async with db_session() as db:
        await db.execute(
            "INSERT OR REPLACE INTO bookmarks (id, user_id, section_id, act, section_number, title, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (bookmark_id, user_id, section_id, act, section_number, title, note, now),
        )
    return bookmark_id


async def get_bookmarks(user_id: str) -> list[dict]:
    """Get all bookmarks for a user."""
    async with db_session() as db:
        cursor = await db.execute(
            "SELECT id, section_id, act, section_number, title, note, created_at "
            "FROM bookmarks WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        return [
            {
                "id": row[0], "section_id": row[1], "act": row[2],
                "section_number": row[3], "title": row[4],
                "note": row[5], "created_at": row[6],
            }
            for row in await cursor.fetchall()
        ]


async def delete_bookmark(bookmark_id: str, user_id: str) -> bool:
    """Delete a bookmark. Returns True if deleted."""
    async with db_session() as db:
        cursor = await db.execute(
            "DELETE FROM bookmarks WHERE id = ? AND user_id = ?",
            (bookmark_id, user_id),
        )
        return cursor.rowcount > 0
