"""
In-Memory TTL Cache — Redis-compatible interface.

High-performance caching layer with:
- TTL-based expiration
- LRU eviction when max entries reached
- Namespace-based key isolation
- Thread-safe operations
"""
from __future__ import annotations
import time
import hashlib
import json
import logging
import threading
from collections import OrderedDict
from typing import Any, Optional

import config

logger = logging.getLogger(__name__)


class _CacheEntry:
    __slots__ = ("value", "expires_at")
    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.expires_at = time.monotonic() + ttl


class InMemoryCache:
    """Thread-safe in-memory cache with TTL and LRU eviction."""

    def __init__(self, max_entries: int = 1000, default_ttl: int = 3600):
        self._store: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._max = max_entries
        self._ttl = default_ttl
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if time.monotonic() > entry.expires_at:
                del self._store[key]
                self._misses += 1
                return None
            self._store.move_to_end(key)
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: int | None = None):
        with self._lock:
            if key in self._store:
                del self._store[key]
            elif len(self._store) >= self._max:
                self._store.popitem(last=False)
            self._store[key] = _CacheEntry(value, ttl or self._ttl)

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def clear(self):
        with self._lock:
            self._store.clear()

    def cleanup_expired(self) -> int:
        now = time.monotonic()
        with self._lock:
            expired = [k for k, v in self._store.items() if now > v.expires_at]
            for k in expired:
                del self._store[k]
        return len(expired)

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "entries": len(self._store),
            "max_entries": self._max,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / max(total, 1), 3),
        }


# ── Singleton Instances ─────────────────────────────────────────────
_query_cache: InMemoryCache | None = None
_llm_cache: InMemoryCache | None = None
_embedding_cache: InMemoryCache | None = None
_rate_limiter: dict[str, list[float]] = {}
_rate_lock = threading.Lock()


def init_cache():
    global _query_cache, _llm_cache, _embedding_cache
    if not config.CACHE_ENABLED:
        logger.info("Cache disabled by configuration")
        return
    _query_cache = InMemoryCache(config.CACHE_MAX_ENTRIES, config.CACHE_TTL_SECONDS)
    _llm_cache = InMemoryCache(config.CACHE_MAX_ENTRIES // 2, config.CACHE_LLM_TTL)
    _embedding_cache = InMemoryCache(config.CACHE_MAX_ENTRIES * 2, config.CACHE_TTL_SECONDS * 4)
    logger.info("✓ Cache initialized (query=%d, llm=%d, embed=%d max)",
                _query_cache._max, _llm_cache._max, _embedding_cache._max)


def make_key(namespace: str, *args) -> str:
    raw = json.dumps([namespace] + list(args), sort_keys=True, ensure_ascii=False)
    return f"{namespace}:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def get_query(key: str) -> Optional[Any]:
    return _query_cache.get(key) if _query_cache else None

def set_query(key: str, value: Any, ttl: int | None = None):
    if _query_cache: _query_cache.set(key, value, ttl)

def get_llm(key: str) -> Optional[Any]:
    return _llm_cache.get(key) if _llm_cache else None

def set_llm(key: str, value: Any, ttl: int | None = None):
    if _llm_cache: _llm_cache.set(key, value, ttl)

def get_embedding(key: str) -> Optional[Any]:
    return _embedding_cache.get(key) if _embedding_cache else None

def set_embedding(key: str, value: Any, ttl: int | None = None):
    if _embedding_cache: _embedding_cache.set(key, value, ttl)


def check_rate_limit(session_id: str, limit: int | None = None) -> bool:
    """Returns True if within rate limit, False if exceeded."""
    max_rpm = limit or config.RATE_LIMIT_PER_MINUTE
    now = time.time()
    with _rate_lock:
        ts = _rate_limiter.get(session_id, [])
        ts = [t for t in ts if now - t < 60]
        if len(ts) >= max_rpm:
            return False
        ts.append(now)
        _rate_limiter[session_id] = ts
        return True


def get_cache_stats() -> dict:
    return {
        "query_cache": _query_cache.stats if _query_cache else None,
        "llm_cache": _llm_cache.stats if _llm_cache else None,
        "embedding_cache": _embedding_cache.stats if _embedding_cache else None,
        "enabled": config.CACHE_ENABLED,
    }
