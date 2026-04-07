"""
Dense Vector Embedding Service — Gemini Embedding API (Async).

Provides:
- Corpus embedding at startup (persisted to disk)
- Query embedding at search time
- NumPy-based cosine similarity search
- Cache integration for embedding vectors
"""
from __future__ import annotations
import logging
import json
import hashlib
from pathlib import Path
from typing import Optional

import numpy as np

import config
from models.schemas import LegalSection
from services import cache

logger = logging.getLogger(__name__)

_client_ready = False
_corpus_embeddings: np.ndarray | None = None
_corpus_sections: list[LegalSection] = []
_embedding_dim: int = 768


def init_embeddings_client(ready: bool):
    """Set the Gemini client reference for embedding calls."""
    global _client_ready
    _client_ready = ready


async def _embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a batch of texts using Gemini embedding API (async)."""
    if not _client_ready:
        raise RuntimeError("Embedding client not initialized")

    from services import gemini_rest

    global _embedding_dim
    all_embeddings = []
    batch_size = 50  # Gemini batch limit

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        try:
            embs = await gemini_rest.embed_content_batch(batch)
            if embs and not all_embeddings:
                _embedding_dim = len(embs[0])
            for emb in embs:
                all_embeddings.append(emb)
        except Exception as e:
            logger.error("Embedding batch %d failed: %s", i // batch_size, e)
            for _ in batch:
                all_embeddings.append([0.0] * _embedding_dim)

    if not all_embeddings:
        return np.zeros((len(texts), _embedding_dim), dtype=np.float32)

    return np.array(all_embeddings, dtype=np.float32)


async def _embed_single(text: str) -> np.ndarray:
    """Embed a single text with caching (async)."""
    cache_key = cache.make_key("embed", text[:500])
    cached = cache.get_embedding(cache_key)
    if cached is not None:
        return np.array(cached, dtype=np.float32)

    if not _client_ready:
        return np.zeros(_embedding_dim, dtype=np.float32)

    try:
        from services import gemini_rest
        vec = await gemini_rest.embed_content(text)
        vec_np = np.array(vec, dtype=np.float32)
        cache.set_embedding(cache_key, vec)
        return vec_np
    except Exception as e:
        logger.error("Single embedding failed: %s", e)
        return np.zeros(_embedding_dim, dtype=np.float32)


async def build_corpus_embeddings(sections: list[LegalSection]) -> int:
    """
    Build or load embeddings for all corpus sections.
    Persists to disk to avoid re-computing on restart.
    """
    global _corpus_embeddings, _corpus_sections, _embedding_dim
    _corpus_sections = sections

    if not sections:
        return 0

    if not _client_ready:
        logger.warning("No embedding client — dense retrieval will be unavailable")
        return 0

    embeddings_dir = config.EMBEDDINGS_DIR
    embeddings_dir.mkdir(parents=True, exist_ok=True)

    # Create a hash of the corpus for cache invalidation
    corpus_hash = hashlib.md5(
        json.dumps([s.id for s in sections], sort_keys=True).encode()
    ).hexdigest()[:12]
    cache_file = embeddings_dir / f"corpus_{corpus_hash}.npy"
    meta_file = embeddings_dir / f"corpus_{corpus_hash}_meta.json"

    # Try loading from disk
    if cache_file.exists() and meta_file.exists():
        try:
            _corpus_embeddings = np.load(str(cache_file))
            meta = json.loads(meta_file.read_text())
            if meta.get("count") == len(sections):
                _embedding_dim = _corpus_embeddings.shape[1]
                logger.info("✓ Loaded cached embeddings: %d vectors (%dd)",
                            len(_corpus_embeddings), _embedding_dim)
                return len(_corpus_embeddings)
        except Exception as e:
            logger.warning("Failed to load cached embeddings: %s", e)

    # Build search texts
    logger.info("Building corpus embeddings for %d sections...", len(sections))
    texts = []
    for sec in sections:
        text = f"{sec.title}. {sec.simplified or sec.text[:300]}"
        texts.append(text)

    _corpus_embeddings = await _embed_texts(texts)
    _embedding_dim = _corpus_embeddings.shape[1] if _corpus_embeddings.shape[0] > 0 else 768

    # Persist to disk
    try:
        np.save(str(cache_file), _corpus_embeddings)
        meta_file.write_text(json.dumps({
            "count": len(sections),
            "dim": _embedding_dim,
            "hash": corpus_hash,
        }))
        logger.info("✓ Corpus embeddings built and cached: %d vectors (%dd)",
                     len(_corpus_embeddings), _embedding_dim)
    except Exception as e:
        logger.warning("Failed to cache embeddings to disk: %s", e)

    return len(_corpus_embeddings)


async def dense_search(query: str, top_k: int = 10) -> list[tuple[LegalSection, float]]:
    """
    Search corpus using dense vector cosine similarity (async).
    Returns list of (LegalSection, similarity_score) tuples.
    """
    if _corpus_embeddings is None or len(_corpus_sections) == 0:
        return []

    query_vec = await _embed_single(query)

    if np.linalg.norm(query_vec) == 0:
        return []

    # Cosine similarity via NumPy
    norms = np.linalg.norm(_corpus_embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)  # avoid div-by-zero
    normalized_corpus = _corpus_embeddings / norms
    normalized_query = query_vec / max(np.linalg.norm(query_vec), 1e-10)

    similarities = normalized_corpus @ normalized_query  # (N,)

    # Get top-k indices
    top_indices = np.argsort(similarities)[::-1][:top_k]

    results = []
    for idx in top_indices:
        score = float(similarities[idx])
        if score > 0.1:  # minimum similarity threshold
            results.append((_corpus_sections[idx], score))

    return results


def get_embedding_stats() -> dict:
    """Get embedding service statistics."""
    return {
        "corpus_vectors": len(_corpus_sections),
        "embedding_dim": _embedding_dim,
        "index_built": _corpus_embeddings is not None,
        "client_ready": _client_ready,
    }
