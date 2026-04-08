"""
Execution Layer — post-processing enrichment of legal responses.

After grounding, this layer enriches the response with:
- Matching procedural workflows
- Relevant government form links
- Authority contact information
- Actionable item detection
"""
from __future__ import annotations
import re
import logging

import config

logger = logging.getLogger(__name__)

# ── Government Form Links (Static Mapping) ─────────────────────
_FORM_LINKS = {
    "fir": {
        "name": "FIR Filing",
        "url": "https://digitalpolice.gov.in",
        "description": "File an FIR online via Digital Police portal",
    },
    "consumer_complaint": {
        "name": "Consumer Complaint",
        "url": "https://consumerhelpline.gov.in",
        "description": "National Consumer Helpline — file complaint online",
    },
    "cyber_crime": {
        "name": "Cyber Crime Report",
        "url": "https://cybercrime.gov.in",
        "description": "Report cyber crime online (financial fraud, harassment)",
    },
    "rti": {
        "name": "RTI Application",
        "url": "https://rtionline.gov.in",
        "description": "File Right to Information application online",
    },
    "epfo": {
        "name": "EPFO Portal",
        "url": "https://www.epfindia.gov.in",
        "description": "Employee Provident Fund — claims, passbook, grievances",
    },
    "labour_complaint": {
        "name": "Labour Complaint",
        "url": "https://shramsuvidha.gov.in",
        "description": "Shram Suvidha — file labour-related complaints",
    },
    "legal_aid": {
        "name": "Free Legal Aid",
        "url": "https://nalsa.gov.in",
        "description": "NALSA — apply for free legal aid (call 15100)",
    },
    "rera_complaint": {
        "name": "RERA Complaint",
        "url": "https://rera.gov.in",
        "description": "Real Estate complaint — contact your state RERA",
    },
    "domestic_violence": {
        "name": "Protection Order",
        "url": "https://ncw.nic.in",
        "description": "National Commission for Women — file complaint online",
    },
    "motor_accident": {
        "name": "Motor Accident Claim",
        "url": "https://morth.nic.in",
        "description": "Ministry of Road Transport — accident claim info",
    },
    "consumer_court": {
        "name": "E-Daakhil",
        "url": "https://edaakhil.nic.in",
        "description": "File consumer court cases online via E-Daakhil portal",
    },
}

# ── Action Keyword → Form Link Mapping ─────────────────────────
_ACTION_KEYWORDS = {
    "fir": ["fir", "first information report", "police complaint", "police station", "file a complaint with police"],
    "consumer_complaint": ["consumer complaint", "consumer helpline", "defective product", "refund"],
    "cyber_crime": ["cyber crime", "online fraud", "cybercrime", "hacking", "phishing", "upi fraud"],
    "rti": ["rti", "right to information", "information request"],
    "labour_complaint": ["labour complaint", "unpaid salary", "wage theft", "wrongful termination"],
    "legal_aid": ["legal aid", "free lawyer", "nalsa", "15100"],
    "rera_complaint": ["rera", "builder complaint", "real estate", "flat possession"],
    "domestic_violence": ["domestic violence", "protection order", "dv act"],
    "motor_accident": ["motor accident", "road accident", "vehicle accident", "accident claim"],
    "consumer_court": ["consumer court", "consumer forum", "consumer case"],
}


def detect_actionable_items(response_text: str) -> list[dict]:
    """
    Scan response for action keywords and link to relevant forms/portals.
    Returns list of matched actionable items with form links.
    """
    text_lower = response_text.lower()
    matched = []
    seen_keys = set()

    for form_key, keywords in _ACTION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower and form_key not in seen_keys:
                form = _FORM_LINKS.get(form_key)
                if form:
                    matched.append({
                        "type": form_key,
                        "name": form["name"],
                        "url": form["url"],
                        "description": form["description"],
                        "matched_keyword": keyword,
                    })
                    seen_keys.add(form_key)
                break

    return matched


def enrich_response(
    response_text: str,
    intent: str = "situational",
    procedures: list[dict] | None = None,
) -> tuple[str, dict]:
    """
    Post-processing enrichment of the final response.
    Appends:
    - Relevant government form/portal links
    - Matching procedural workflows (if any)

    Returns: (enriched_text, execution_metadata)

    Args:
        response_text: The LLM-generated response text
        intent: Query intent from analysis
        procedures: Available procedural workflows (from procedures router)
    """
    if not config.EXECUTION_LAYER_ENABLED:
        return response_text, {"execution_layer": "disabled"}

    metadata = {
        "execution_layer": "active",
        "forms_linked": [],
        "procedures_matched": [],
    }

    enriched = response_text

    # 1. Detect and append relevant form links
    actionable_items = detect_actionable_items(response_text)
    if actionable_items:
        enriched += "\n\n### 🔗 Relevant Government Portals\n"
        for item in actionable_items[:4]:  # Max 4 links
            enriched += f"- **[{item['name']}]({item['url']})** — {item['description']}\n"
            metadata["forms_linked"].append(item["type"])

    # 2. Match procedural workflows (if available and intent is procedural)
    if procedures and intent == "procedural":
        text_lower = response_text.lower()
        for proc in procedures[:10]:  # Check top 10 procedures
            proc_title = proc.get("title", "").lower()
            proc_keywords = proc_title.split()
            # Simple matching: if 2+ words from procedure title appear in response
            match_count = sum(1 for w in proc_keywords if w in text_lower)
            if match_count >= 2:
                metadata["procedures_matched"].append(proc.get("id", ""))

    return enriched, metadata


def get_form_links() -> dict:
    """Get all available form links (for API exposure)."""
    return _FORM_LINKS
