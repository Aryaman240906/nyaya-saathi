"""
Multilingual Language Pipeline.

Handles:
- Language detection (English, Hindi, Hinglish)
- Hinglish normalization
- Translation to canonical English for retrieval
- Back-translation for response delivery
"""
from __future__ import annotations
import logging
import re

logger = logging.getLogger(__name__)

# ── Language detection ──────────────────────────────────────────────

# Common Hindi words / Devanagari detection
_DEVANAGARI_RANGE = re.compile(r'[\u0900-\u097F]')
_HINGLISH_MARKERS = {
    "kya", "hai", "mein", "ko", "ka", "ki", "ke", "se", "par", "ho",
    "hain", "tha", "thi", "the", "kaise", "kab", "kaha", "kyu", "kyun",
    "nahi", "nhi", "mat", "aur", "ya", "bhi", "woh", "yeh", "ye",
    "kuch", "sab", "bahut", "zyada", "kam", "accha", "bura", "theek",
    "mujhe", "tujhe", "humko", "unko", "isko", "usko", "apna", "apni",
    "mere", "tera", "hamara", "unka", "inka", "koi", "kaun", "konsa",
    "jab", "tab", "agar", "toh", "phir", "lekin", "magar", "kyunki",
    "isliye", "waise", "jaise", "chahiye", "sakta", "sakti", "sakte",
    "karna", "dena", "lena", "jana", "aana", "hona", "raha", "rahi",
    "darj", "shikayat", "kanoon", "adhikar", "nyay", "police", "thana",
    "petition", "aadhaar", "paisa", "rupaye", "complaint", "fir",
}


def detect_language(text: str) -> str:
    """
    Detect input language.
    Returns: 'hi' (Hindi), 'hinglish' (code-mixed), or 'en' (English)
    """
    # Check for Devanagari script
    devanagari_chars = len(_DEVANAGARI_RANGE.findall(text))
    total_alpha = len(re.findall(r'[a-zA-Z\u0900-\u097F]', text))

    if total_alpha == 0:
        return "en"

    devanagari_ratio = devanagari_chars / total_alpha

    if devanagari_ratio > 0.5:
        return "hi"

    # Check for Hinglish (Latin script with Hindi words)
    words = text.lower().split()
    if not words:
        return "en"

    hinglish_count = sum(1 for w in words if w.strip(".,!?;:") in _HINGLISH_MARKERS)
    hinglish_ratio = hinglish_count / len(words)

    if hinglish_ratio > 0.15:
        return "hinglish"

    return "en"


def normalize_hinglish(text: str) -> str:
    """
    Normalize Hinglish text for better retrieval.
    Maps common Hinglish legal terms to English equivalents.
    """
    mappings = {
        "fir": "FIR first information report",
        "thana": "police station",
        "kanoon": "law",
        "adalat": "court",
        "adhikar": "right rights",
        "nyay": "justice",
        "shikayat": "complaint",
        "darj": "file register",
        "paisa": "money",
        "rupaye": "rupees money",
        "dhokha": "fraud cheating",
        "maar": "assault beat",
        "chori": "theft steal",
        "zameen": "land property",
        "ghar": "house home",
        "malik": "owner landlord",
        "kiraya": "rent",
        "naukri": "job employment",
        "tankhwah": "salary wages",
        "doctor": "doctor medical",
        "dawa": "medicine",
        "shaadi": "marriage wedding",
        "talaq": "divorce",
        "baccha": "child children",
        "aurat": "woman",
        "ladki": "girl woman",
        "budha": "elderly old",
        "sarkaar": "government",
        "sarkar": "government",
        "afsar": "officer official",
        "vakil": "lawyer advocate",
        "judge": "judge",
        "jail": "jail prison imprisonment",
        "saza": "punishment sentence",
        "jurmana": "fine penalty",
        "karz": "debt loan",
        "bank": "bank",
        "cyber": "cyber online internet",
        "online": "online internet cyber",
        "dhamki": "threat intimidation",
        "harassment": "harassment",
        "pareshan": "harassment trouble",
    }

    words = text.split()
    normalized = []
    for word in words:
        clean = word.lower().strip(".,!?;:")
        if clean in mappings:
            normalized.append(mappings[clean])
        else:
            normalized.append(word)

    return " ".join(normalized)


def prepare_query_for_retrieval(text: str, detected_lang: str) -> str:
    """
    Prepare user query for BM25 retrieval.
    Normalizes Hinglish, keeps English as-is.
    Hindi (Devanagari) queries need LLM translation (handled in reasoning.py).
    """
    if detected_lang == "hinglish":
        return normalize_hinglish(text)
    return text


def get_response_language_instruction(lang: str) -> str:
    """Get LLM instruction for response language."""
    if lang == "hi":
        return (
            "CRITICAL LANGUAGE INSTRUCTION:\n"
            "- You MUST write the ENTIRE response in Hindi (Devanagari script).\n"
            "- Ensure that ALL output fields, including string and array values in the JSON (like action steps, your_rights, etc), are fully translated to Hindi.\n"
            "- Use simple, everyday Hindi that a common citizen can understand. Avoid overly formal or Sanskritized Hindi.\n"
            "- Do NOT leave any bullet points or instructions in English."
        )
    elif lang == "hinglish":
        return (
            "CRITICAL LANGUAGE INSTRUCTION:\n"
            "- You MUST write the ENTIRE response in Hinglish (Hindi dialog written in English alphabet).\n"
            "- Ensure that ALL output fields and arrays in the JSON (like action steps, your_rights, etc) are in Hinglish.\n"
            "- Use a conversational, friendly tone. Legal terms can remain in English."
        )
    else:
        return (
            "CRITICAL LANGUAGE INSTRUCTION:\n"
            "- Respond in clear, simple English.\n"
            "- Avoid legal jargon where possible. Use plain language that any citizen can understand."
        )
