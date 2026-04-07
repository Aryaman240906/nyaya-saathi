"""
Async REST client for Gemini API using httpx.

Fully async — no blocking calls in the event loop.
Features:
- Connection pooling via httpx.AsyncClient
- Exponential backoff with jitter for 429s
- Circuit breaker for consecutive failures
- Structured error types
"""
from __future__ import annotations
import asyncio
import json
import logging
import random
import time
from typing import AsyncGenerator

import httpx

import config
from services import cache

logger = logging.getLogger(__name__)

# ── Singleton async client ──────────────────────────────────────────
_client: httpx.AsyncClient | None = None
_circuit_failures: int = 0
_CIRCUIT_THRESHOLD: int = 5
_circuit_open_until: float = 0


def _get_client() -> httpx.AsyncClient:
    """Get or create the singleton async HTTP client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            http2=False,
        )
    return _client


async def close_client():
    """Close the HTTP client on shutdown."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


def _get_url(endpoint: str) -> str:
    if not config.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set.")
    base = "https://generativelanguage.googleapis.com/v1beta/models"
    return f"{base}/{config.GEMINI_MODEL}:{endpoint}?key={config.GEMINI_API_KEY}"


def _get_embedding_url() -> str:
    if not config.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set.")
    base = "https://generativelanguage.googleapis.com/v1beta/models"
    return f"{base}/{config.GEMINI_EMBEDDING_MODEL}:embedContent?key={config.GEMINI_API_KEY}"


def _check_circuit():
    """Check if circuit breaker is open."""
    global _circuit_failures, _circuit_open_until
    if _circuit_failures >= _CIRCUIT_THRESHOLD:
        if time.monotonic() < _circuit_open_until:
            raise RuntimeError("Circuit breaker OPEN — Gemini API unavailable. Retrying in a moment.")
        # Reset after cooldown
        _circuit_failures = 0


def _record_success():
    """Record a successful call — resets circuit breaker."""
    global _circuit_failures
    _circuit_failures = 0


def _record_failure():
    """Record a failed call — may trip circuit breaker."""
    global _circuit_failures, _circuit_open_until
    _circuit_failures += 1
    if _circuit_failures >= _CIRCUIT_THRESHOLD:
        _circuit_open_until = time.monotonic() + 30  # 30s cooldown
        logger.error("Circuit breaker TRIPPED after %d consecutive failures", _circuit_failures)


async def _call_with_retry(
    url: str,
    body: dict,
    stream: bool = False,
    max_retries: int = 1,
    timeout: float = 60.0,
) -> httpx.Response:
    """Execute request with fast failover for 429s."""
    _check_circuit()
    client = _get_client()
    retry_delay = 1.0

    for i in range(max_retries + 1):
        try:
            if stream:
                # For streaming, we need to use the stream context
                req = client.build_request("POST", url, json=body)
                resp = await client.send(req, stream=True)
            else:
                resp = await client.post(url, json=body, timeout=timeout)

            if resp.status_code == 429 or resp.status_code >= 500:
                if i < max_retries:
                    jitter = random.uniform(0, 1)
                    wait = retry_delay + jitter
                    logger.warning("Gemini %s received. Retrying in %.1fs...", resp.status_code, wait)
                    if stream:
                        await resp.aclose()
                    await asyncio.sleep(wait)
                    retry_delay *= 2
                    continue
                _record_failure()
            else:
                _record_success()

            return resp

        except httpx.TimeoutException:
            if i < max_retries:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
                continue
            _record_failure()
            raise
        except Exception as e:
            _record_failure()
            logger.error("Request failed: %s", e)
            raise

    return resp


async def generate_content(
    contents: list[dict],
    system_instruction: str = "",
    temperature: float = 0.3,
    max_output_tokens: int = 4096,
    response_mime_type: str = "text/plain",
) -> str:
    """Async generation with caching."""
    # Build cache key
    cache_payload = {
        "contents": contents,
        "system_instruction": system_instruction,
        "temp": temperature,
        "model": config.GEMINI_MODEL,
    }
    cache_key = cache.make_key("llm_gen", json.dumps(cache_payload, sort_keys=True))

    if config.CACHE_ENABLED:
        cached = cache.get_llm(cache_key)
        if cached:
            return cached

    url = _get_url("generateContent")
    body = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
            "topP": 0.8,
            "responseMimeType": response_mime_type,
        },
    }

    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    resp = await _call_with_retry(url, body)

    if resp.status_code != 200:
        logger.error("Gemini API error: %s", resp.text)
        raise RuntimeError(f"Gemini API returned {resp.status_code}: {resp.text}")

    data = resp.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        if config.CACHE_ENABLED and text:
            cache.set_llm(cache_key, text)
        return text
    except (KeyError, IndexError):
        return ""


async def generate_content_stream(
    contents: list[dict],
    system_instruction: str = "",
    temperature: float = 0.3,
    max_output_tokens: int = 4096,
) -> AsyncGenerator[str, None]:
    """Async generator for streaming responses."""
    url = _get_url("streamGenerateContent")
    url += "&alt=sse"

    body = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
            "topP": 0.8,
        },
    }

    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    resp = await _call_with_retry(url, body, stream=True)

    if resp.status_code != 200:
        error_text = ""
        try:
            async for chunk in resp.aiter_text():
                error_text += chunk
        finally:
            await resp.aclose()
        logger.error("Gemini stream error: %s", error_text)
        raise RuntimeError(f"Gemini API returned {resp.status_code}")

    try:
        async for line in resp.aiter_lines():
            if line and line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    text = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                    )
                    if text:
                        yield text
                except Exception:
                    pass
    finally:
        await resp.aclose()


async def embed_content(text: str) -> list[float]:
    """Get embedding with backoff."""
    url = _get_embedding_url()
    body = {
        "model": f"models/{config.GEMINI_EMBEDDING_MODEL}",
        "content": {"parts": [{"text": text}]},
    }

    resp = await _call_with_retry(url, body, timeout=15.0)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API returned {resp.status_code}")

    data = resp.json()
    return data.get("embedding", {}).get("values", [])


async def embed_content_batch(texts: list[str]) -> list[list[float]]:
    """Batch embed with backoff."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_EMBEDDING_MODEL}:batchEmbedContents?key={config.GEMINI_API_KEY}"
    )

    requests_payload = [
        {
            "model": f"models/{config.GEMINI_EMBEDDING_MODEL}",
            "content": {"parts": [{"text": t}]},
        }
        for t in texts
    ]

    body = {"requests": requests_payload}

    resp = await _call_with_retry(url, body)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API returned {resp.status_code}")

    data = resp.json()
    return [emb.get("values", []) for emb in data.get("embeddings", [])]
