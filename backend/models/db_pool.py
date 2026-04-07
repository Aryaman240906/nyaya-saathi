"""
Async SQLite Connection Pool.

Provides a singleton connection manager with:
- WAL mode for concurrent reads
- Context manager for clean lifecycle
- Automatic initialization
"""
from __future__ import annotations
import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

_db_path: Path | None = None
_initialized = False


async def init_pool(db_path: Path):
    """Initialize the connection pool with WAL mode."""
    global _db_path, _initialized
    _db_path = db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Enable WAL mode for better concurrent read performance
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA cache_size=-64000")  # 64MB cache
        await db.execute("PRAGMA foreign_keys=ON")
        await db.commit()

    _initialized = True
    logger.info("✓ DB pool initialized (WAL mode) at %s", db_path)


async def get_db() -> aiosqlite.Connection:
    """Get a database connection. Caller must use as async context manager."""
    if not _db_path:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    db = await aiosqlite.connect(str(_db_path))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    return db


class DBSession:
    """Async context manager for database sessions with automatic cleanup."""

    def __init__(self):
        self._db: aiosqlite.Connection | None = None

    async def __aenter__(self) -> aiosqlite.Connection:
        self._db = await get_db()
        return self._db

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._db:
            if exc_type is None:
                await self._db.commit()
            await self._db.close()
            self._db = None
        return False


def db_session() -> DBSession:
    """Create a new database session context manager."""
    return DBSession()
