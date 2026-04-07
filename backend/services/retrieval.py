"""
Tri-Modal Retrieval Engine.

Three retrieval streams:
1. BM25 sparse keyword retrieval
2. Dense vector similarity (Gemini embeddings)
3. Structured document navigation

Plus: cross-reference graph traversal and corpus gap detection.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import List, Optional

import bm25s
import snowballstemmer

from models.schemas import LegalSection, Source
from services import cache

logger = logging.getLogger(__name__)

# ── Module-level state ──────────────────────────────────────────────
_corpus_sections: list[LegalSection] = []
_corpus_texts: list[str] = []
_retriever: bm25s.BM25 | None = None
_stemmer = snowballstemmer.stemmer("english")


def load_corpus(corpus_dir: Path) -> int:
    """Load all JSON corpus files and build BM25 index."""
    global _corpus_sections, _corpus_texts, _retriever

    _corpus_sections = []
    _corpus_texts = []

    if not corpus_dir.exists():
        logger.warning("Corpus directory %s does not exist", corpus_dir)
        return 0

    for json_file in sorted(corpus_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            sections = data.get("sections", [])
            short_name = data.get("short_name", "")
            act_name = data.get("act", "")

            for sec in sections:
                section = LegalSection(
                    id=sec.get("id", ""),
                    act=act_name,
                    short_name=short_name,
                    section_number=sec.get("section_number", ""),
                    title=sec.get("title", ""),
                    chapter=sec.get("chapter", ""),
                    text=sec.get("text", ""),
                    simplified=sec.get("simplified", ""),
                    related_sections=sec.get("related_sections", []),
                    keywords=sec.get("keywords", []),
                    category=sec.get("category", ""),
                    subcategory=sec.get("subcategory", ""),
                    punishment=sec.get("punishment", ""),
                )
                _corpus_sections.append(section)

                search_text = " ".join([
                    section.title, section.title,
                    " ".join(section.keywords), " ".join(section.keywords),
                    section.text, section.simplified,
                    section.section_number, section.short_name,
                    section.category, section.subcategory,
                ])
                _corpus_texts.append(search_text)

            logger.info("Loaded %d sections from %s", len(sections), json_file.name)
        except Exception as e:
            logger.error("Failed to load %s: %s", json_file.name, e)

    if _corpus_texts:
        _retriever = bm25s.BM25()
        tokenized = bm25s.tokenize(_corpus_texts, stemmer=_stemmer, stopwords="en")
        _retriever.index(tokenized)
        logger.info("BM25 index built with %d documents", len(_corpus_texts))

    return len(_corpus_sections)


def get_corpus_sections() -> list[LegalSection]:
    """Get all loaded corpus sections (for embedding service)."""
    return _corpus_sections


def search(query: str, top_k: int = 10) -> list[tuple[LegalSection, float]]:
    """BM25 keyword retrieval."""
    # Check cache
    cache_key = cache.make_key("bm25", query, top_k)
    cached = cache.get_query(cache_key)
    if cached is not None:
        return cached

    if _retriever is None or not _corpus_sections:
        return []

    tokenized_query = bm25s.tokenize([query], stemmer=_stemmer, stopwords="en")
    results, scores = _retriever.retrieve(tokenized_query, k=min(top_k, len(_corpus_sections)))

    output = []
    for idx, score in zip(results[0], scores[0]):
        idx = int(idx)
        if 0 <= idx < len(_corpus_sections) and float(score) > 0:
            output.append((_corpus_sections[idx], float(score)))

    cache.set_query(cache_key, output)
    return output


def multi_query_search(queries: list[str], top_k: int = 10) -> list[tuple[LegalSection, float]]:
    """
    Search with multiple expanded queries and merge results.
    Used by query expansion to combine synonym variants.
    """
    all_results: dict[str, tuple[LegalSection, float]] = {}

    for query in queries:
        results = search(query, top_k=top_k)
        for section, score in results:
            if section.id not in all_results or score > all_results[section.id][1]:
                all_results[section.id] = (section, score)

    merged = sorted(all_results.values(), key=lambda x: x[1], reverse=True)
    return merged[:top_k]


def cross_reference_search(seed_sections: list[LegalSection], depth: int = 1) -> list[tuple[LegalSection, float]]:
    """
    Graph traversal: follow cross-references from seed sections.
    Returns related sections with decaying scores based on distance.
    """
    visited = {s.id for s in seed_sections}
    results = []
    current_level = seed_sections
    base_score = 0.7

    for d in range(depth):
        next_level = []
        score = base_score * (0.7 ** d)  # Decay with depth

        for sec in current_level:
            for ref_id in sec.related_sections:
                if ref_id not in visited:
                    found = search_by_section(ref_id)
                    if found:
                        results.append((found, score))
                        visited.add(ref_id)
                        next_level.append(found)

        current_level = next_level

    return results


def detect_corpus_gap(
    bm25_results: list[tuple[LegalSection, float]],
    dense_results: list[tuple[LegalSection, float]],
    struct_results: list[tuple[LegalSection, float]],
    threshold: float = 0.15,
) -> dict:
    """
    Corpus Gap Detector: identifies when retrieval quality is insufficient.
    Returns gap analysis with recommendations.
    """
    bm25_top = bm25_results[0][1] if bm25_results else 0
    dense_top = dense_results[0][1] if dense_results else 0
    struct_top = struct_results[0][1] if struct_results else 0

    has_gap = all(s < threshold for s in [bm25_top, struct_top])
    agreement = len(set(r[0].id for r in bm25_results[:3]) &
                     set(r[0].id for r in dense_results[:3]))

    return {
        "has_gap": has_gap,
        "bm25_top_score": round(bm25_top, 4),
        "dense_top_score": round(dense_top, 4),
        "structured_top_score": round(struct_top, 4),
        "stream_agreement": agreement,
        "recommendation": (
            "low_confidence" if has_gap else
            "high_confidence" if agreement >= 2 else
            "moderate_confidence"
        ),
    }


def search_by_section(section_id: str) -> Optional[LegalSection]:
    for sec in _corpus_sections:
        if sec.id == section_id:
            return sec
    return None


def search_by_act(short_name: str) -> list[LegalSection]:
    return [s for s in _corpus_sections if s.short_name.lower() == short_name.lower()]


def get_related_sections(section: LegalSection) -> list[LegalSection]:
    related = []
    for ref_id in section.related_sections:
        found = search_by_section(ref_id)
        if found:
            related.append(found)
    return related


def get_all_categories() -> list[str]:
    return list(set(s.category for s in _corpus_sections if s.category))


def get_corpus_stats() -> dict:
    acts = set(s.short_name for s in _corpus_sections)
    categories = set(s.category for s in _corpus_sections if s.category)
    return {
        "total_sections": len(_corpus_sections),
        "acts": sorted(acts),
        "categories": sorted(categories),
        "index_built": _retriever is not None,
    }
