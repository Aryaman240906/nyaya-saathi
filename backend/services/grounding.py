"""
Enhanced Grounding Validator + Critic Layer.

Ensures LLM responses are grounded in retrieved legal context:
- Citation validation (Section Verifier)
- Hard grounding mode (strip ungrounded citations)
- Haiku Critic (lightweight quality check)
- Pydantic schema enforcement
- Confidence scoring with multi-factor analysis (retrieval + agreement + grounding)
- Uncertainty injection with "consult lawyer" hints
"""
from __future__ import annotations
import re
import logging

from models.schemas import LegalSection
import config

logger = logging.getLogger(__name__)

_client_ready = False


def init_grounding_client(ready: bool):
    """Set the Gemini client for Haiku Critic."""
    global _client_ready
    _client_ready = ready


def validate_citations(
    response_text: str,
    retrieved_sections: list[LegalSection],
) -> dict:
    """
    Check if legal citations in the response match retrieved context.
    Enhanced with section-to-act cross-referencing.
    """
    cited_sections = set()
    patterns = [
        r'[Ss]ection\s+(\d+[A-Za-z]*)',
        r'[Aa]rticle\s+(\d+[A-Za-z]*)',
        r'(?:IPC|CrPC|BNS|CPA|IT\s*Act)\s+[Ss](?:ection|ec\.?)\s*(\d+[A-Za-z]*)',
        r'[Ss]ec\.\s*(\d+[A-Za-z]*)',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, response_text)
        cited_sections.update(matches)

    retrieved_section_numbers = {s.section_number for s in retrieved_sections}
    retrieved_ids = {s.id for s in retrieved_sections}

    grounded = cited_sections & retrieved_section_numbers
    ungrounded = cited_sections - retrieved_section_numbers

    # Check if ungrounded sections appear in related_sections
    all_related = set()
    for s in retrieved_sections:
        for ref in s.related_sections:
            # Extract section number from ref like "ipc_302" → "302"
            match = re.search(r'(\d+[A-Za-z]*)', ref)
            if match:
                all_related.add(match.group(1))

    loosely_grounded = ungrounded & all_related
    truly_ungrounded = ungrounded - all_related

    grounding_ratio = len(grounded | loosely_grounded) / max(len(cited_sections), 1)

    return {
        "total_citations": len(cited_sections),
        "grounded_citations": len(grounded),
        "loosely_grounded": len(loosely_grounded),
        "ungrounded_citations": list(truly_ungrounded),
        "grounding_ratio": round(grounding_ratio, 2),
        "is_grounded": grounding_ratio >= 0.7,
        "cited_sections": list(cited_sections),
    }


# ── Hard Grounding ──────────────────────────────────────────────
def hard_grounding_check(
    response_text: str,
    retrieved_sections: list[LegalSection],
    grounding_report: dict | None = None,
) -> tuple[str, dict]:
    """
    Hard grounding step: verify citations against corpus.
    If grounding is weak, strip ungrounded citations from the response.

    Returns:
        (sanitized_response_text, updated_grounding_report)
    """
    if not config.GROUNDING_HARD_MODE:
        report = grounding_report or validate_citations(response_text, retrieved_sections)
        return response_text, report

    if grounding_report is None:
        grounding_report = validate_citations(response_text, retrieved_sections)

    ungrounded = grounding_report.get("ungrounded_citations", [])

    if not ungrounded:
        return response_text, grounding_report

    # Strip ungrounded citations from response text
    sanitized = response_text
    for sec_num in ungrounded:
        # Remove patterns like "Section 999", "Sec. 999", "section 999"
        sanitized = re.sub(
            rf'\b[Ss](?:ection|ec\.?)\s+{re.escape(sec_num)}\b',
            f'[citation removed]',
            sanitized,
        )

    # Add a note if citations were stripped
    if sanitized != response_text:
        stripped_count = len(ungrounded)
        note = (
            f"\n\n> ⚠️ *{stripped_count} citation(s) were removed because they could not be "
            f"verified against the retrieved legal database. Only verified citations are shown.*\n"
        )
        sanitized += note
        grounding_report["hard_grounding_applied"] = True
        grounding_report["citations_stripped"] = stripped_count
        logger.info("Hard grounding: stripped %d ungrounded citations", stripped_count)

    return sanitized, grounding_report


def compute_confidence(
    retrieval_scores: list[float],
    grounding_report: dict,
    has_context: bool,
    debate_confidence: float | None = None,
    stream_agreement: int = 0,
    gap_analysis: dict | None = None,
) -> float:
    """
    Enhanced confidence scoring with multiple factors:
    - Retrieval quality (0-0.25)
    - Grounding ratio (0-0.25)
    - Context availability (0-0.1)
    - Debate consensus (0-0.2) — if debate mode
    - Stream agreement (0-0.1) — how many retrieval streams agree
    - Gap analysis (0-0.1) — corpus gap detector output
    """
    if not has_context:
        return 0.1

    # Retrieval score component (0-0.25)
    if retrieval_scores:
        avg_retrieval = sum(retrieval_scores[:5]) / len(retrieval_scores[:5])
        retrieval_component = min(avg_retrieval * 6, 0.25)
    else:
        retrieval_component = 0.0

    # Grounding component (0-0.25)
    grounding_component = grounding_report.get("grounding_ratio", 0) * 0.25

    # Context component (0-0.1)
    context_component = 0.1 if has_context else 0.0

    # Debate consensus component (0-0.2)
    if debate_confidence is not None:
        debate_component = debate_confidence * 0.2
    else:
        debate_component = 0.08  # Default for simple mode

    # Stream agreement (0-0.1)
    # How many retrieval streams have overlapping top-3 results
    agreement_component = min(stream_agreement * 0.033, 0.1)

    # Gap analysis (0-0.1)
    gap_component = 0.0
    if gap_analysis:
        if not gap_analysis.get("has_gap", True):
            gap_component = 0.1
        elif gap_analysis.get("stream_agreement", 0) >= 1:
            gap_component = 0.05

    confidence = (
        retrieval_component +
        grounding_component +
        context_component +
        debate_component +
        agreement_component +
        gap_component
    )
    return round(min(confidence, 1.0), 2)


async def haiku_critic(
    response_text: str,
    query: str,
    context: str,
) -> dict:
    """
    Lightweight Haiku Critic — fast quality evaluation.
    Uses a minimal prompt to check for obvious issues.
    """
    if not _client_ready or not response_text:
        return {"score": 0.7, "issues": [], "skipped": True}

    try:
        from services import gemini_rest
        prompt = (
            f"Rate this legal response on a scale of 1-10 for accuracy, completeness, "
            f"and clarity. List any factual issues. Be very brief.\n\n"
            f"Query: {query[:200]}\n"
            f"Response: {response_text[:1000]}\n\n"
            f"Output JSON: {{\"score\": N, \"issues\": [\"issue1\"], \"assessment\": \"brief text\"}}"
        )
        response = await gemini_rest.generate_content(
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            temperature=0.1,
            max_output_tokens=200,
            response_mime_type="application/json",
        )
        import json
        parsed = json.loads(response.strip())
        return {
            "score": parsed.get("score", 7) / 10,
            "issues": parsed.get("issues", []),
            "assessment": parsed.get("assessment", ""),
        }
    except Exception as e:
        logger.debug("Haiku critic failed: %s", e)
        return {"score": 0.7, "issues": [], "skipped": True}


def inject_uncertainty(text: str, confidence: float) -> str:
    """Add uncertainty markers for low-confidence responses.
    Enhanced with stronger 'consult lawyer' messaging below LOW_CONFIDENCE_THRESHOLD.
    """
    threshold = config.LOW_CONFIDENCE_THRESHOLD

    if confidence < threshold * 0.6:
        # Very low confidence — strong warning
        prefix = (
            "⚠️ **Important Notice:** I could not find sufficiently relevant legal provisions "
            "for your specific query in my database. The following information is **general in nature** "
            "and may not accurately address your situation.\n\n"
            "📞 **Please consult a qualified lawyer** for precise legal advice. "
            "You can reach **NALSA Legal Aid at 15100** (toll-free) for free legal assistance.\n\n"
            "---\n\n"
        )
        return prefix + text
    elif confidence < threshold:
        # Low confidence — moderate warning
        prefix = (
            "📋 **Note:** Based on the available legal provisions, here is what I found. "
            "Some aspects may require further legal consultation for complete accuracy.\n\n"
            "💡 *For personalized legal advice, consider calling NALSA Legal Aid at 15100.*\n\n"
        )
        return prefix + text

    return text


def add_disclaimer(text: str) -> str:
    """Append standard legal disclaimer."""
    disclaimer = (
        "\n\n---\n"
        "⚖️ *Disclaimer: This information is provided for educational and awareness "
        "purposes only. It does not constitute legal advice. For specific legal matters, "
        "please consult a qualified advocate. You can reach NALSA Legal Aid at 15100 "
        "for free legal assistance.*"
    )
    return text + disclaimer
