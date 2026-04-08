"""
Cross-Reference Index — static graph built at startup.

Provides O(1) lookups for:
- Forward references (section → related sections)
- Reverse references (section → sections that reference it)
- Related acts (section → acts that cross-reference it)
"""
from __future__ import annotations
import logging
from collections import defaultdict

from models.schemas import LegalSection

logger = logging.getLogger(__name__)

# ── Module-level index ──────────────────────────────────────────
_forward_refs: dict[str, list[str]] = {}
_reverse_refs: dict[str, list[str]] = defaultdict(list)
_section_to_act: dict[str, str] = {}
_built = False


def build_index(sections: list[LegalSection]) -> None:
    """Build the cross-reference index from corpus sections."""
    global _forward_refs, _reverse_refs, _section_to_act, _built

    _forward_refs = {}
    _reverse_refs = defaultdict(list)
    _section_to_act = {}

    for sec in sections:
        _forward_refs[sec.id] = list(sec.related_sections)
        _section_to_act[sec.id] = sec.short_name

        for ref_id in sec.related_sections:
            _reverse_refs[ref_id].append(sec.id)

    _built = True

    total_forward = sum(len(v) for v in _forward_refs.values())
    total_reverse = sum(len(v) for v in _reverse_refs.values())
    logger.info(
        "✓ Cross-reference index: %d sections, %d forward refs, %d reverse refs",
        len(_forward_refs), total_forward, total_reverse,
    )


def get_cross_refs(section_id: str) -> list[str]:
    """Get forward cross-references for a section (O(1))."""
    return _forward_refs.get(section_id, [])


def get_reverse_refs(section_id: str) -> list[str]:
    """Get sections that reference this section (O(1))."""
    return _reverse_refs.get(section_id, [])


def get_related_acts(section_id: str) -> list[str]:
    """Get acts that are related to this section via cross-references."""
    related_ids = _forward_refs.get(section_id, []) + _reverse_refs.get(section_id, [])
    acts = set()
    for rid in related_ids:
        if rid in _section_to_act:
            acts.add(_section_to_act[rid])
    # Exclude the section's own act
    own_act = _section_to_act.get(section_id, "")
    acts.discard(own_act)
    return sorted(acts)


def get_enriched_refs(section_id: str) -> dict:
    """Get full cross-reference data for a section."""
    return {
        "forward": get_cross_refs(section_id),
        "reverse": get_reverse_refs(section_id),
        "related_acts": get_related_acts(section_id),
    }


def is_built() -> bool:
    return _built


def get_stats() -> dict:
    return {
        "built": _built,
        "sections_indexed": len(_forward_refs),
        "total_forward_refs": sum(len(v) for v in _forward_refs.values()),
        "total_reverse_refs": sum(len(v) for v in _reverse_refs.values()),
    }
