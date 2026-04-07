"""
Structured Document Tree Navigator.

Provides hierarchical navigation over the legal corpus using
Act → Chapter → Section → Clause structure, enabling precise
section lookup without reliance on embedding similarity.
"""
from __future__ import annotations
import logging
from collections import defaultdict
from typing import Optional

from models.schemas import LegalSection
from services import retrieval

logger = logging.getLogger(__name__)

# ── Hierarchical Tree ───────────────────────────────────────────────
# Structure: { act_short_name: { chapter: [LegalSection, ...] } }
_tree: dict[str, dict[str, list[LegalSection]]] = {}


def build_tree():
    """Build the hierarchical document tree from loaded corpus."""
    global _tree
    _tree = defaultdict(lambda: defaultdict(list))

    stats = retrieval.get_corpus_stats()
    for act_short in stats.get("acts", []):
        sections = retrieval.search_by_act(act_short)
        for sec in sections:
            chapter = sec.chapter or "General"
            _tree[act_short][chapter].append(sec)

    logger.info(
        "Document tree built: %d acts, %d total chapters",
        len(_tree),
        sum(len(chapters) for chapters in _tree.values()),
    )


def navigate_to_section(act: str, section_number: str) -> Optional[LegalSection]:
    """Direct navigation: Act + Section Number → LegalSection."""
    act_upper = act.upper()
    for short_name, chapters in _tree.items():
        if short_name.upper() == act_upper:
            for chapter_sections in chapters.values():
                for sec in chapter_sections:
                    if sec.section_number == section_number:
                        return sec
    return None


def find_sections_by_keywords_in_act(act: str, keywords: list[str]) -> list[LegalSection]:
    """Find sections within a specific act matching given keywords."""
    act_upper = act.upper()
    results = []
    for short_name, chapters in _tree.items():
        if short_name.upper() == act_upper:
            for chapter_sections in chapters.values():
                for sec in chapter_sections:
                    sec_text = f"{sec.title} {sec.text} {' '.join(sec.keywords)}".lower()
                    if any(kw.lower() in sec_text for kw in keywords):
                        results.append(sec)
    return results


def get_chapter_sections(act: str, chapter: str) -> list[LegalSection]:
    """Get all sections in a specific chapter of an act."""
    act_upper = act.upper()
    for short_name, chapters in _tree.items():
        if short_name.upper() == act_upper:
            for ch_name, sections in chapters.items():
                if chapter.lower() in ch_name.lower():
                    return sections
    return []


def get_tree_summary() -> dict:
    """Get a summary of the document tree structure."""
    summary = {}
    for act, chapters in _tree.items():
        summary[act] = {
            ch: len(sections) for ch, sections in chapters.items()
        }
    return summary


def cross_reference_lookup(section: LegalSection) -> list[LegalSection]:
    """Follow cross-references from a section to find related provisions."""
    results = []
    for ref_id in section.related_sections:
        found = retrieval.search_by_section(ref_id)
        if found:
            results.append(found)
    return results


def structured_search(query: str, act_hint: str = "", top_k: int = 5) -> list[tuple[LegalSection, float]]:
    """
    Structured navigation search — uses document tree hierarchy
    to find relevant sections. Complementary to BM25.
    
    Scoring: exact section match (1.0) > keyword in title (0.8) > keyword in text (0.5)
    """
    results: list[tuple[LegalSection, float]] = []
    query_lower = query.lower()
    query_words = query_lower.split()

    # 1. Check for direct section references (e.g., "Section 302 IPC")
    import re
    section_pattern = re.compile(r'section\s+(\d+[a-zA-Z]*)', re.IGNORECASE)
    matches = section_pattern.findall(query)
    for sec_num in matches:
        for act, chapters in _tree.items():
            if act_hint and act.upper() != act_hint.upper():
                continue
            for chapter_sections in chapters.values():
                for sec in chapter_sections:
                    if sec.section_number == sec_num:
                        results.append((sec, 1.0))

    # 2. Check for article references (Constitution)
    article_pattern = re.compile(r'article\s+(\d+[a-zA-Z]*)', re.IGNORECASE)
    art_matches = article_pattern.findall(query)
    for art_num in art_matches:
        for act, chapters in _tree.items():
            if act.upper() not in ("CONSTITUTION", "COI"):
                continue
            for chapter_sections in chapters.values():
                for sec in chapter_sections:
                    if sec.section_number == art_num:
                        results.append((sec, 1.0))

    # 3. Keyword matching in titles (high relevance)
    for act, chapters in _tree.items():
        if act_hint and act.upper() != act_hint.upper():
            continue
        for chapter_sections in chapters.values():
            for sec in chapter_sections:
                title_lower = sec.title.lower()
                keyword_match = sum(1 for w in query_words if w in title_lower)
                if keyword_match >= 2 or (keyword_match == 1 and len(query_words) <= 3):
                    score = 0.8 * (keyword_match / max(len(query_words), 1))
                    if (sec, score) not in results:
                        results.append((sec, score))

    # 4. Keyword matching in section keywords
    for act, chapters in _tree.items():
        if act_hint and act.upper() != act_hint.upper():
            continue
        for chapter_sections in chapters.values():
            for sec in chapter_sections:
                sec_keywords = [k.lower() for k in sec.keywords]
                keyword_match = sum(1 for w in query_words if w in sec_keywords)
                if keyword_match >= 1:
                    score = 0.6 * (keyword_match / max(len(query_words), 1))
                    existing = [r for r in results if r[0].id == sec.id]
                    if not existing:
                        results.append((sec, score))

    # Deduplicate and sort
    seen = set()
    unique_results = []
    for sec, score in sorted(results, key=lambda x: x[1], reverse=True):
        if sec.id not in seen:
            seen.add(sec.id)
            unique_results.append((sec, score))

    return unique_results[:top_k]
