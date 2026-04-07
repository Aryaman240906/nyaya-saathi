"""
Enhanced Reciprocal Rank Fusion — 4-stream weighted RRF.

Merges results from:
1. BM25 sparse retrieval
2. Dense vector similarity
3. Structured document navigation
4. Cross-reference graph traversal

With configurable per-stream weights and Haiku reranking.
"""
from __future__ import annotations
import logging
from models.schemas import LegalSection, Source
import config

logger = logging.getLogger(__name__)

RRF_K = 60


def fuse(
    bm25_results: list[tuple[LegalSection, float]],
    structured_results: list[tuple[LegalSection, float]],
    top_k: int = 10,
    dense_results: list[tuple[LegalSection, float]] | None = None,
    cross_ref_results: list[tuple[LegalSection, float]] | None = None,
) -> list[tuple[LegalSection, float, str]]:
    """
    Weighted Reciprocal Rank Fusion across up to 4 retrieval streams.
    Returns: list of (LegalSection, fused_score, best_retrieval_method) tuples.
    """
    rrf_scores: dict[str, float] = {}
    section_map: dict[str, LegalSection] = {}
    method_map: dict[str, set] = {}

    def _score_stream(results, method: str, weight: float):
        for rank, (section, score) in enumerate(results, start=1):
            sid = section.id
            rrf_scores[sid] = rrf_scores.get(sid, 0) + weight * (1.0 / (RRF_K + rank))
            section_map[sid] = section
            method_map.setdefault(sid, set()).add(method)

    # Score each stream with its weight
    _score_stream(bm25_results, "bm25", config.WEIGHT_BM25)
    _score_stream(structured_results, "structured", config.WEIGHT_STRUCTURED)

    if dense_results:
        _score_stream(dense_results, "dense", config.WEIGHT_DENSE)

    if cross_ref_results:
        _score_stream(cross_ref_results, "cross_ref", config.WEIGHT_CROSS_REF)

    # Sort by fused score
    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    output = []
    for sid, score in ranked[:top_k]:
        section = section_map[sid]
        methods = method_map.get(sid, set())
        if len(methods) > 1:
            method = "fused"
        else:
            method = next(iter(methods))
        output.append((section, score, method))

    streams_used = sum([
        1,  # BM25 always
        1,  # Structured always
        1 if dense_results else 0,
        1 if cross_ref_results else 0,
    ])

    logger.debug("RRF fusion: %d streams → %d fused results (top=%.4f)",
                 streams_used, len(output), output[0][1] if output else 0)

    return output


def results_to_sources(
    fused_results: list[tuple[LegalSection, float, str]]
) -> list[Source]:
    """Convert fused results to Source objects for API response."""
    return [
        Source(
            act=section.act,
            section=f"Section {section.section_number}",
            title=section.title,
            relevance_score=round(score, 4),
            retrieval_method=method,
        )
        for section, score, method in fused_results
    ]


def build_context(
    fused_results: list[tuple[LegalSection, float, str]],
    max_chars: int = 8000,
) -> str:
    """Build context string from fused results for LLM consumption."""
    context_parts = []
    char_count = 0

    for section, score, method in fused_results:
        # Use HTML Details/Summary block for beautiful native accordions in Next.js via rehype-raw
        entry = (
            f"<details class=\"mb-4 bg-white/5 border border-white/10 rounded-xl overflow-hidden\">\n"
            f"<summary class=\"px-4 py-3 cursor-pointer text-sm font-semibold text-indigo-300 hover:bg-white/5 transition-colors list-none flex items-center justify-between\">\n"
            f"<span>🏛️ {section.short_name} Section {section.section_number}: {section.title}</span>\n"
            f"</summary>\n"
            f"<div class=\"px-4 pb-4 pt-1 text-sm text-zinc-300 space-y-3\">\n\n"
            f"**📝 Legal Text:**\n"
            f"> {section.text}\n\n"
            f"**💡 Simplified Analysis:**\n"
            f"> {section.simplified}\n\n"
            f"*Category:* {section.category}\n"
        )
        if section.punishment:
            entry += f"*Punishment:* {section.punishment}\n\n"
        if section.related_sections:
            entry += f"*Related Acts:* {', '.join(section.related_sections)}\n\n"
        entry += "</div>\n</details>\n\n"

        if char_count + len(entry) > max_chars:
            break
        context_parts.append(entry)
        char_count += len(entry)

    return "\n".join(context_parts)
