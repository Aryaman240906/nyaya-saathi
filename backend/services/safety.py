"""
Safety Gate + Urgency Detection.

Detects:
- Jailbreak/misuse attempts
- Emergency/violence/threat scenarios
- Urgent safety situations requiring immediate action
"""
from __future__ import annotations
import re
import logging
from models.schemas import UrgencyInfo

logger = logging.getLogger(__name__)

# ── Jailbreak Detection ────────────────────────────────────────────
_JAILBREAK_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+(instructions|rules|prompts)",
    r"you\s+are\s+now\s+(a|an)\s+(?!legal|law)",
    r"pretend\s+(you\s+are|to\s+be)\s+(?!a\s+(lawyer|advocate|legal))",
    r"forget\s+(everything|all|your)\s+(you|rules|instructions)",
    r"override\s+(your|the)\s+(rules|instructions|safety)",
    r"bypass\s+(the\s+)?(restrictions|safety|filters)",
    r"act\s+as\s+if\s+you\s+have\s+no\s+(restrictions|rules)",
    r"dan\s+mode",
    r"developer\s+mode",
]

# ── Urgency Keywords ───────────────────────────────────────────────
_CRITICAL_PATTERNS = {
    "violence": [
        r"\b(beat|beating|hit|hitting|attack|attacked|assault|assaulted)\b",
        r"\b(murder|kill|killed|killing|stab|stabbed)\b",
        r"\b(rape|raped|raping|molest|molested|sexual\s+assault)\b",
        r"\b(domestic\s+violence|wife\s+beating|husband\s+beating)\b",
        r"\b(abuse|abused|abusing|torture|tortured)\b",
        r"\b(kidnap|kidnapped|abduct|abducted)\b",
        r"\b(threatening\s+to\s+kill|death\s+threat)\b",
        # Hindi/Hinglish
        r"\b(maar|mara|peet|peeta|maarta)\b",
        r"\b(jaanseemaarna|dhamki)\b",
    ],
    "fraud_scam": [
        r"\b(fraud|scam|scammed|cheated|cheat|swindle)\b",
        r"\b(money\s+stolen|bank\s+fraud|online\s+fraud)\b",
        r"\b(identity\s+theft|phishing|hacked)\b",
        r"\b(upi\s+fraud|credit\s+card\s+fraud|loan\s+fraud)\b",
        r"\b(ponzi|mlm\s+scam|investment\s+fraud)\b",
        # Hinglish
        r"\b(dhokha|thagi|loot)\b",
    ],
    "harassment": [
        r"\b(harass|harassed|harassment|stalking|stalked)\b",
        r"\b(workplace\s+harassment|sexual\s+harassment)\b",
        r"\b(eve\s+teasing|cyber\s+bullying|cyberbullying)\b",
        r"\b(blackmail|blackmailed|extortion)\b",
        # Hinglish
        r"\b(pareshan|tang)\b",
    ],
    "child_safety": [
        r"\b(child\s+abuse|child\s+labour|child\s+marriage)\b",
        r"\b(minor|underage|juvenile)\b.*\b(abuse|assault|exploit)\b",
        r"\b(pocso|child\s+trafficking)\b",
    ],
    "threat": [
        r"\b(threat|threatened|threatening)\b",
        r"\b(extort|extortion|ransom)\b",
        r"\b(coerce|coercion|forced|forcing)\b",
        r"\b(dhamki|dharamki)\b",
    ],
}

_HIGH_PATTERNS = {
    "consumer_fraud": [
        r"\b(defective\s+product|consumer\s+complaint|refund\s+denied)\b",
        r"\b(overcharged|price\s+gouging|false\s+advertising)\b",
    ],
    "workplace_issues": [
        r"\b(wrongful\s+termination|unpaid\s+salary|wage\s+theft)\b",
        r"\b(fired\s+illegally|forced\s+resignation)\b",
    ],
    "property_dispute": [
        r"\b(evict|evicted|eviction|illegal\s+possession)\b",
        r"\b(land\s+grab|property\s+fraud|encroachment)\b",
    ],
}

# ── Helplines Database ─────────────────────────────────────────────
HELPLINES = {
    "emergency": {"name": "Police Emergency", "number": "112", "description": "All emergencies"},
    "women": {"name": "Women Helpline", "number": "181", "description": "Women in distress"},
    "women_ncw": {"name": "NCW Helpline", "number": "7827-170-170", "description": "National Commission for Women"},
    "child": {"name": "CHILDLINE", "number": "1098", "description": "Child abuse/distress"},
    "cyber": {"name": "Cyber Crime Helpline", "number": "1930", "description": "Online fraud/cybercrime"},
    "cyber_portal": {"name": "Cyber Crime Portal", "number": "cybercrime.gov.in", "description": "Online complaint filing"},
    "domestic_violence": {"name": "Domestic Violence", "number": "181", "description": "Domestic violence support"},
    "legal_aid": {"name": "NALSA Legal Aid", "number": "15100", "description": "Free legal aid"},
    "senior_citizen": {"name": "Elder Abuse Helpline", "number": "14567", "description": "Senior citizen helpline"},
    "consumer": {"name": "Consumer Helpline", "number": "1800-11-4000", "description": "Consumer grievances"},
    "labour": {"name": "Labour Helpline", "number": "14434", "description": "Labour disputes/wages"},
    "human_rights": {"name": "NHRC Helpline", "number": "14433", "description": "Human rights violations"},
}


def check_jailbreak(text: str) -> bool:
    """Check if input contains jailbreak/prompt injection attempts."""
    text_lower = text.lower()
    for pattern in _JAILBREAK_PATTERNS:
        if re.search(pattern, text_lower):
            logger.warning("Jailbreak attempt detected: %s", text[:100])
            return True
    return False


def detect_urgency(text: str) -> UrgencyInfo:
    """Detect urgency level and return appropriate response information."""
    text_lower = text.lower()

    # Check CRITICAL patterns
    for category, patterns in _CRITICAL_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return _build_urgency_response("critical", category)

    # Check HIGH patterns
    for category, patterns in _HIGH_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return _build_urgency_response("high", category)

    return UrgencyInfo(level="low")


def _build_urgency_response(level: str, category: str) -> UrgencyInfo:
    """Build urgency response with appropriate helplines and actions."""
    helplines_map = {
        "violence": ["emergency", "women", "legal_aid"],
        "fraud_scam": ["emergency", "cyber", "cyber_portal"],
        "harassment": ["women", "women_ncw", "legal_aid", "cyber"],
        "child_safety": ["child", "emergency", "legal_aid"],
        "threat": ["emergency", "legal_aid"],
        "consumer_fraud": ["consumer", "legal_aid"],
        "workplace_issues": ["labour", "legal_aid"],
        "property_dispute": ["legal_aid", "emergency"],
    }

    actions_map = {
        "violence": [
            "Call 112 immediately if you are in immediate danger",
            "Go to the nearest police station to file an FIR",
            "Document injuries with photographs if possible",
            "Seek medical attention for any injuries",
            "Contact a women's shelter or safe house if needed",
        ],
        "fraud_scam": [
            "File a complaint at cybercrime.gov.in immediately",
            "Call 1930 (Cyber Crime Helpline) to report the fraud",
            "Contact your bank to freeze/block the affected account",
            "Do NOT share any more OTPs, passwords, or personal information",
            "Save all evidence: screenshots, messages, transaction IDs",
        ],
        "harassment": [
            "Document all incidents with dates, times, and evidence",
            "File a complaint with the Internal Complaints Committee (workplace)",
            "File a police complaint if it involves criminal behavior",
            "Contact NCW helpline at 7827-170-170 for guidance",
        ],
        "child_safety": [
            "Call CHILDLINE at 1098 immediately",
            "Call 112 if the child is in immediate danger",
            "Report to the nearest Child Welfare Committee",
            "File a complaint under POCSO Act at the police station",
        ],
        "threat": [
            "Call 112 if you are in immediate danger",
            "File an FIR at the nearest police station",
            "Save all evidence of threats (messages, recordings, witnesses)",
            "Inform a trusted family member or friend",
        ],
        "consumer_fraud": [
            "File a complaint on the National Consumer Helpline portal",
            "Call 1800-11-4000 for guidance",
            "Gather all bills, receipts, and communications as evidence",
        ],
        "workplace_issues": [
            "Document all evidence of the violation",
            "File a complaint with the Labour Commissioner",
            "Call 14434 (Labour Helpline) for guidance",
        ],
        "property_dispute": [
            "Gather all property documents and evidence of ownership",
            "File a police complaint if there is illegal possession",
            "Consult with a legal aid lawyer (call 15100)",
        ],
    }

    messages_map = {
        "violence": "⚠️ This appears to be an urgent safety situation. Your safety is the top priority.",
        "fraud_scam": "🚨 Financial fraud detected. Time is critical — act immediately to minimize losses.",
        "harassment": "⚠️ Harassment is a serious offence. You have legal protections — here's what to do.",
        "child_safety": "🚨 URGENT: Child safety concern detected. Immediate action is required.",
        "threat": "⚠️ Threats are a criminal offence. Your safety comes first.",
        "consumer_fraud": "📋 Consumer rights violation detected. You have strong legal protections.",
        "workplace_issues": "📋 Workplace violation detected. Labour laws protect your rights.",
        "property_dispute": "📋 Property dispute detected. Document everything and seek legal help.",
    }

    relevant_helplines = [
        HELPLINES[h] for h in helplines_map.get(category, ["emergency", "legal_aid"])
        if h in HELPLINES
    ]

    return UrgencyInfo(
        level=level,
        message=messages_map.get(category, "Please review the situation carefully."),
        helplines=relevant_helplines,
        immediate_actions=actions_map.get(category, []),
    )
