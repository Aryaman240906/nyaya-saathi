"""
Audit Logging Service.

Tracks all system interactions for safety, compliance, and debugging:
- Query audit trails
- Safety gate decisions
- LLM interaction logs
- Jailbreak attempt records
"""
from __future__ import annotations
import json
import logging
import time
from datetime import datetime, timezone

import config

logger = logging.getLogger(__name__)

_audit_buffer: list[dict] = []
_DB_PATH = None


async def init_audit(db_path):
    """Initialize audit table in the database."""
    global _DB_PATH
    _DB_PATH = db_path
    import aiosqlite
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                session_id TEXT,
                data TEXT DEFAULT '{}',
                severity TEXT DEFAULT 'info',
                latency_ms REAL DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_type
            ON audit_log(event_type, timestamp)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_session
            ON audit_log(session_id, timestamp)
        """)
        await db.commit()
    logger.info("✓ Audit logging initialized")


async def log_event(
    event_type: str,
    session_id: str = "",
    data: dict | None = None,
    severity: str = "info",
    latency_ms: float = 0,
):
    """Log an audit event."""
    if not config.AUDIT_ENABLED or not _DB_PATH:
        return

    try:
        import aiosqlite
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(str(_DB_PATH)) as db:
            await db.execute(
                "INSERT INTO audit_log (timestamp, event_type, session_id, data, severity, latency_ms) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now, event_type, session_id, json.dumps(data or {}), severity, latency_ms),
            )
            await db.commit()
    except Exception as e:
        logger.error("Audit log write failed: %s", e)


async def log_query(session_id: str, query: str, language: str, urgency: str):
    """Log an incoming query."""
    await log_event("query", session_id, {
        "query_length": len(query),
        "language": language,
        "urgency": urgency,
    })


async def log_safety(session_id: str, verdict: str, details: dict | None = None):
    """Log a safety gate decision."""
    severity = "warning" if verdict == "blocked" else "info"
    await log_event("safety", session_id, {
        "verdict": verdict,
        **(details or {}),
    }, severity=severity)


async def log_llm_call(
    session_id: str,
    model: str,
    agent: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: float = 0,
):
    """Log an LLM API call."""
    await log_event("llm_call", session_id, {
        "model": model,
        "agent": agent,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }, latency_ms=latency_ms)


async def log_debate(session_id: str, debate_data: dict):
    """Log a debate engine execution."""
    await log_event("debate", session_id, debate_data)


async def log_jailbreak(session_id: str, query_snippet: str):
    """Log a jailbreak attempt."""
    await log_event("jailbreak", session_id, {
        "query_snippet": query_snippet[:200],
    }, severity="critical")


async def get_audit_stats() -> dict:
    """Get audit log statistics."""
    if not _DB_PATH:
        return {"enabled": False}
    try:
        import aiosqlite
        async with aiosqlite.connect(str(_DB_PATH)) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM audit_log")
            total = (await cursor.fetchone())[0]
            cursor = await db.execute(
                "SELECT event_type, COUNT(*) FROM audit_log GROUP BY event_type"
            )
            by_type = {row[0]: row[1] for row in await cursor.fetchall()}
            cursor = await db.execute(
                "SELECT COUNT(*) FROM audit_log WHERE severity = 'critical'"
            )
            critical = (await cursor.fetchone())[0]
            return {
                "enabled": True,
                "total_events": total,
                "by_type": by_type,
                "critical_events": critical,
            }
    except Exception:
        return {"enabled": True, "error": "Could not read audit stats"}
