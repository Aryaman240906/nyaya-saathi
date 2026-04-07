"""
Advanced Query Engine.

Replaces simple query preparation with:
- Semantic Clarifier: detects vague queries, reformulates
- Multi-Party Detector: identifies multiple actors/subjects
- Query Expansion: generates synonym permutations
- State Router: routes to appropriate pipeline branch
"""
from __future__ import annotations
import re
import logging
from typing import Optional
from enum import Enum

from models.schemas import QueryAnalysis
from services.language import detect_language, normalize_hinglish
import config

logger = logging.getLogger(__name__)

_client_ready = False


def init_query_engine(ready: bool):
    """Set the LLM client ready state for query intelligence."""
    global _client_ready
    _client_ready = ready


class QueryIntent(str, Enum):
    FACTUAL = "factual"           # "What is Section 302?"
    SITUATIONAL = "situational"   # "Someone stole my phone"
    PROCEDURAL = "procedural"     # "How to file an FIR?"
    RIGHTS = "rights"             # "What are my rights as a tenant?"
    COMPARATIVE = "comparative"   # "Difference between IPC and BNS?"
    DOCUMENT = "document"         # "Analyze this notice..."
    GENERAL = "general"           # Catch-all


# ── Intent Detection (Rule-Based + Fast) ────────────────────────────
_PROCEDURAL_MARKERS = [
    r"\bhow\s+to\b", r"\bsteps?\s+(to|for)\b", r"\bprocess\s+(of|for|to)\b",
    r"\bprocedure\b", r"\bfile\s+(a|an|the)?\b", r"\bapply\s+for\b",
    r"\bwhere\s+to\s+(go|report|complain)\b", r"\bkaise\b", r"\btarika\b",
]

_FACTUAL_MARKERS = [
    r"\bwhat\s+is\b", r"\bdefine\b", r"\bmeaning\s+of\b",
    r"\bsection\s+\d+\b", r"\barticle\s+\d+\b", r"\bexplain\b",
    r"\bpunishment\s+for\b",
]

_RIGHTS_MARKERS = [
    r"\b(my|our|citizen|worker|consumer|women|woman)\s+rights?\b",
    r"\bright\s+to\b", r"\badhikar\b", r"\blegal\s+rights?\b",
]

_COMPARATIVE_MARKERS = [
    r"\bdifference\s+between\b", r"\bvs\.?\b", r"\bcompare\b",
    r"\bold\s+(law|ipc)\s+vs\b", r"\bnew\s+law\b",
]


def detect_intent(query: str) -> QueryIntent:
    """Fast rule-based intent detection."""
    q = query.lower()
    for p in _PROCEDURAL_MARKERS:
        if re.search(p, q): return QueryIntent.PROCEDURAL
    for p in _FACTUAL_MARKERS:
        if re.search(p, q): return QueryIntent.FACTUAL
    for p in _RIGHTS_MARKERS:
        if re.search(p, q): return QueryIntent.RIGHTS
    for p in _COMPARATIVE_MARKERS:
        if re.search(p, q): return QueryIntent.COMPARATIVE
    return QueryIntent.SITUATIONAL  # Most common for real users


# ── Vagueness Detection ─────────────────────────────────────────────
_VAGUE_PATTERNS = [
    r"^(help|problem|issue|legal|law|kuch|batao|bolo)\s*\.?$",
    r"^.{1,15}$",  # Very short queries
]


def is_vague(query: str) -> bool:
    """Check if the query is too vague to process effectively."""
    q = query.strip().lower()
    if len(q.split()) <= 2 and not re.search(r'section\s+\d+|article\s+\d+', q):
        return True
    for p in _VAGUE_PATTERNS:
        if re.match(p, q):
            return True
    return False


# ── Semantic Clarifier ──────────────────────────────────────────────
async def clarify_query(query: str) -> str:
    """Use LLM to reformulate a vague query into a precise legal query."""
    if not _client_ready or not config.SEMANTIC_CLARIFIER_ENABLED:
        return query

    try:
        from services import gemini_rest
        prompt = (
            f"The following is a vague legal query from an Indian citizen. "
            f"Reformulate it into a clear, specific legal question that can be "
            f"answered using Indian law. Output ONLY the reformulated question.\n\n"
            f"Vague query: {query}"
        )
        clarified = await gemini_rest.generate_content(
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            temperature=0.1,
            max_output_tokens=150,
        )
        clarified = clarified.strip()

        if clarified and len(clarified) > len(query):
            logger.info("Clarified query: '%s' → '%s'", query[:50], clarified[:80])
            return clarified
    except Exception as e:
        logger.error("Semantic clarification failed: %s", e)

    return query


# ── Multi-Party Detection ───────────────────────────────────────────
def detect_parties(query: str) -> list[str]:
    """Identify distinct parties/actors mentioned in the query."""
    parties = []
    q = query.lower()

    party_patterns = {
        "complainant": [r"\bi\b", r"\bmy\b", r"\bme\b", r"\bmain\b", r"\bmera\b", r"\bmujhe\b"],
        "accused": [r"\bhe\b.*\b(did|stole|hit|beat|cheat)", r"\baccused\b", r"\bdefendant\b"],
        "employer": [r"\b(employer|boss|company|manager)\b", r"\bmalik\b"],
        "spouse": [r"\b(husband|wife|spouse)\b", r"\bpati\b", r"\bpatni\b"],
        "police": [r"\b(police|officer|constable)\b", r"\bpulice\b"],
        "landlord": [r"\b(landlord|owner|property\s+owner)\b", r"\bmakan\s*malik\b"],
        "minor": [r"\b(child|minor|kid|son|daughter)\b", r"\bbaccha\b"],
    }

    for party, patterns in party_patterns.items():
        for p in patterns:
            if re.search(p, q):
                parties.append(party)
                break

    return parties or ["complainant"]


# ── Query Expansion ─────────────────────────────────────────────────
_LEGAL_SYNONYMS = {
    "steal": ["theft", "larceny", "stolen", "chori", "robbery"],
    "theft": ["steal", "stolen", "larceny", "robbery", "chori"],
    "cheat": ["fraud", "cheating", "swindle", "scam", "dhoka"],
    "fraud": ["cheat", "cheating", "scam", "swindle", "forgery"],
    "beat": ["assault", "hurt", "attack", "battery", "marpeet"],
    "assault": ["beat", "hurt", "attack", "battery", "violence"],
    "murder": ["kill", "homicide", "culpable homicide", "hatya"],
    "rape": ["sexual assault", "sexual offence"],
    "divorce": ["marriage dissolution", "talaq", "separation"],
    "bail": ["release", "surety", "zamanat"],
    "fir": ["first information report", "police complaint", "police report"],
    "arrest": ["detention", "custody", "giraftari"],
    "eviction": ["forced removal", "illegal eviction", "dispossession"],
    "dowry": ["dahej", "dowry harassment", "498a"],
    "harassment": ["stalking", "teasing", "bullying", "pareshan"],
    "salary": ["wages", "pay", "compensation", "tankhwah"],
    "refund": ["return", "money back", "consumer complaint"],
    "cybercrime": ["online fraud", "hacking", "phishing", "cyber crime"],
    "property": ["land", "real estate", "zameen", "immovable property"],
    "tenant": ["renter", "lessee", "kirayedar"],
    "accident": ["collision", "crash", "motor accident", "road accident"],
    "maintenance": ["alimony", "support", "nafaqa"],
    "cheque": ["check", "dishonour", "bounce", "138"],
    "rti": ["right to information", "information request"],
    "builder": ["developer", "promoter", "real estate"],
    "domestic violence": ["dv", "marital cruelty", "dowry harassment"],
    "child abuse": ["pocso", "child sexual abuse", "minor abuse"],
    "discrimination": ["caste", "untouchability", "atrocity"],
    "drugs": ["ndps", "narcotic", "narcotics", "substance"],
}


def expand_query(query: str) -> list[str]:
    """Generate expanded query variants using legal synonyms."""
    if not config.QUERY_EXPANSION_ENABLED:
        return [query]

    expansions = [query]  # Original always first
    words = query.lower().split()

    for word in words:
        clean = word.strip(".,!?;:")
        if clean in _LEGAL_SYNONYMS:
            for synonym in _LEGAL_SYNONYMS[clean][:2]:
                expanded = query.lower().replace(clean, synonym, 1)
                if expanded != query.lower() and expanded not in expansions:
                    expansions.append(expanded)
                    if len(expansions) >= config.MAX_EXPANDED_QUERIES:
                        return expansions

    return expansions[:config.MAX_EXPANDED_QUERIES]


# ── Full Analysis Pipeline ──────────────────────────────────────────
async def analyze_query(query: str, detected_lang: str = "en") -> QueryAnalysis:
    """
    Full query analysis pipeline:
    1. Intent detection
    2. Vagueness check + semantic clarification
    3. Multi-party detection
    4. Query expansion
    5. Language normalization
    """
    intent = detect_intent(query)
    parties = detect_parties(query)
    vague = is_vague(query)

    # Clarify if vague
    effective_query = query
    if vague:
        effective_query = await clarify_query(query)

    # Normalize if Hinglish
    retrieval_query = effective_query
    if detected_lang == "hinglish":
        retrieval_query = normalize_hinglish(effective_query)

    # Expand
    expanded = expand_query(retrieval_query)

    return QueryAnalysis(
        original_query=query,
        effective_query=effective_query,
        retrieval_queries=expanded,
        intent=intent.value,
        parties=parties,
        is_vague=vague,
        was_clarified=vague and effective_query != query,
        language=detected_lang,
    )
