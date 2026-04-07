"""Pipeline introspection router — pipeline state, debate history, system stats."""
from __future__ import annotations
import logging

from fastapi import APIRouter

from services import cache, retrieval, embeddings
from services.audit import get_audit_stats

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.get("/stats")
async def pipeline_stats():
    """Get full system statistics: corpus, cache, embeddings, audit."""
    corpus_stats = retrieval.get_corpus_stats()
    cache_stats = cache.get_cache_stats()
    embedding_stats = embeddings.get_embedding_stats()
    audit_stats = await get_audit_stats()

    return {
        "corpus": corpus_stats,
        "cache": cache_stats,
        "embeddings": embedding_stats,
        "audit": audit_stats,
    }


@router.get("/nodes")
async def pipeline_nodes():
    """Get pipeline node definitions for canvas visualization."""
    return {
        "nodes": [
            {"id": "safety", "name": "Safety Gate", "type": "gate", "color": "#EF4444",
             "description": "Jailbreak detection & rule enforcement"},
            {"id": "query_engine", "name": "Query Engine", "type": "processor", "color": "#8B5CF6",
             "description": "Intent detection, clarification, expansion"},
            {"id": "language", "name": "Language", "type": "processor", "color": "#06B6D4",
             "description": "Detection & normalization (EN/HI/Hinglish)"},
            {"id": "bm25", "name": "BM25 Retrieval", "type": "retrieval", "color": "#6366F1",
             "description": "Sparse keyword search"},
            {"id": "dense", "name": "Dense Vectors", "type": "retrieval", "color": "#6366F1",
             "description": "Gemini embedding similarity"},
            {"id": "structured", "name": "Structured Nav", "type": "retrieval", "color": "#6366F1",
             "description": "Hierarchical document tree"},
            {"id": "cross_ref", "name": "Cross-Reference", "type": "retrieval", "color": "#6366F1",
             "description": "Graph traversal of related sections"},
            {"id": "fusion", "name": "RRF Fusion", "type": "processor", "color": "#F59E0B",
             "description": "4-stream weighted fusion & dedup"},
            {"id": "prosecutor", "name": "Prosecutor", "type": "agent", "color": "#10B981",
             "description": "Domain specialist — primary analysis"},
            {"id": "defense", "name": "Defense", "type": "agent", "color": "#8B5CF6",
             "description": "Cross-domain challenger"},
            {"id": "validator", "name": "Validator", "type": "agent", "color": "#F59E0B",
             "description": "Judge — final synthesis"},
            {"id": "grounding", "name": "Grounding", "type": "validator", "color": "#EF4444",
             "description": "Citation validation & confidence"},
        ],
        "edges": [
            {"from": "safety", "to": "query_engine"},
            {"from": "query_engine", "to": "language"},
            {"from": "language", "to": "bm25"},
            {"from": "language", "to": "dense"},
            {"from": "language", "to": "structured"},
            {"from": "bm25", "to": "fusion"},
            {"from": "dense", "to": "fusion"},
            {"from": "structured", "to": "fusion"},
            {"from": "cross_ref", "to": "fusion"},
            {"from": "fusion", "to": "prosecutor"},
            {"from": "prosecutor", "to": "defense"},
            {"from": "defense", "to": "validator"},
            {"from": "validator", "to": "grounding"},
        ],
    }
