"""
NYAYA-SAATHI Backend — FastAPI Application Entry Point.

AI-Native Multilingual Legal Assistance System
Tri-Modal RAG + Multi-Agent Debate Architecture
v3.0 — Auth + History + Expanded Corpus
"""
from __future__ import annotations
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from models.database import init_db
from services import retrieval, structured_nav, cache, embeddings
from services.reasoning import init_client
from services.audit import init_audit
from services.gemini_rest import close_client as close_gemini_client
from middleware import register_middleware
from routers import chat, procedures, rights, documents, pipeline, auth, sessions, bookmarks
from routers.procedures import load_procedures

# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-25s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("nyaya-saathi")


# ── Lifespan ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    start = time.monotonic()
    logger.info("=" * 60)
    logger.info("  NYAYA-SAATHI 3.0 — Starting up...")
    logger.info("=" * 60)

    # 1. Initialize database (with migrations for existing DBs)
    await init_db(config.DATABASE_PATH)
    logger.info("✓ Database initialized at %s", config.DATABASE_PATH)

    # 2. Initialize audit logging
    await init_audit(config.DATABASE_PATH)

    # 3. Initialize cache
    cache.init_cache()

    # 4. Load legal corpus and build BM25 index
    corpus_count = retrieval.load_corpus(config.CORPUS_DIR)
    logger.info("✓ Legal corpus loaded: %d sections", corpus_count)

    # 5. Build structured document tree
    structured_nav.build_tree()
    tree_summary = structured_nav.get_tree_summary()
    logger.info("✓ Document tree built: %s", {k: sum(v.values()) for k, v in tree_summary.items()})

    # 6. Load procedural workflows
    load_procedures()
    logger.info("✓ Procedural workflows loaded")

    # 7. Initialize Gemini client + all dependent services
    init_client()
    logger.info("✓ LLM client initialized (model: %s)", config.GEMINI_MODEL)

    # 8. Build dense vector embeddings
    corpus_sections = retrieval.get_corpus_sections()
    embed_count = await embeddings.build_corpus_embeddings(corpus_sections)
    logger.info("✓ Dense embeddings: %d vectors", embed_count)

    elapsed = (time.monotonic() - start) * 1000
    logger.info("=" * 60)
    logger.info("  NYAYA-SAATHI 3.0 — Ready! (%.0fms startup)", elapsed)
    logger.info("  Pipeline: Safety → Query Engine → Tri-Modal RAG → Debate → Grounding")
    logger.info("  Debate Engine: %s", "ENABLED" if config.DEBATE_ENABLED else "DISABLED")
    logger.info("  Cache: %s", "ENABLED" if config.CACHE_ENABLED else "DISABLED")
    logger.info("  Auth: JWT | Anonymous: %s", "ALLOWED" if config.ALLOW_ANONYMOUS else "DISABLED")
    logger.info("=" * 60)

    yield

    # Graceful shutdown
    logger.info("NYAYA-SAATHI — Shutting down...")
    await close_gemini_client()
    logger.info("✓ HTTP client closed")


# ── App Creation ────────────────────────────────────────────────────
app = FastAPI(
    title="NYAYA-SAATHI 3.0 API",
    description=(
        "AI-Native Multilingual Legal Assistance System. "
        "Tri-Modal RAG + Multi-Agent Debate Architecture for citizen-centric legal awareness. "
        "v3.0 — JWT Auth, Chat History, 16+ Legal Acts."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

# ── Middleware ──────────────────────────────────────────────────────
register_middleware(app)

# ── CORS ────────────────────────────────────────────────────────────
# ── CORS ────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all (fixes CORS)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(bookmarks.router)
app.include_router(procedures.router)
app.include_router(rights.router)
app.include_router(documents.router)
app.include_router(pipeline.router)


# ── Health Check ────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    """Health check endpoint."""
    stats = retrieval.get_corpus_stats()
    embed_stats = embeddings.get_embedding_stats()
    cache_stats = cache.get_cache_stats()
    return {
        "status": "healthy",
        "service": "nyaya-saathi",
        "version": "3.0.0",
        "corpus": stats,
        "embeddings": embed_stats,
        "cache": cache_stats,
        "llm_configured": bool(config.GEMINI_API_KEY),
        "debate_enabled": config.DEBATE_ENABLED,
        "auth_enabled": True,
        "anonymous_allowed": config.ALLOW_ANONYMOUS,
    }


@app.get("/api/stats")
async def stats():
    """Get corpus and system statistics."""
    corpus_stats = retrieval.get_corpus_stats()
    tree_summary = structured_nav.get_tree_summary()
    embed_stats = embeddings.get_embedding_stats()
    return {
        "corpus": corpus_stats,
        "tree": tree_summary,
        "embeddings": embed_stats,
    }
