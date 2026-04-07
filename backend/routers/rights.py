"""Rights explorer router — browse and search legal rights by category."""
from __future__ import annotations
import logging

from fastapi import APIRouter, Query

from services import retrieval

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rights", tags=["rights"])

# Curated rights categories with common search queries
RIGHTS_CATEGORIES = {
    "fundamental": {
        "title": "Fundamental Rights",
        "title_hi": "मौलिक अधिकार",
        "description": "Constitutional rights guaranteed to every Indian citizen",
        "icon": "⚖️",
        "acts": ["CONSTITUTION", "COI"],
    },
    "criminal": {
        "title": "Criminal Rights",
        "title_hi": "आपराधिक अधिकार",
        "description": "Rights of accused persons, victims, and witnesses",
        "icon": "🛡️",
        "acts": ["IPC", "CRPC", "BNS"],
    },
    "consumer": {
        "title": "Consumer Rights",
        "title_hi": "उपभोक्ता अधिकार",
        "description": "Protection against unfair trade practices and defective goods",
        "icon": "🛒",
        "acts": ["CPA"],
    },
    "cyber": {
        "title": "Cyber & Digital Rights",
        "title_hi": "साइबर अधिकार",
        "description": "Online privacy, data protection, and cybercrime laws",
        "icon": "💻",
        "acts": ["ITA"],
    },
    "women": {
        "title": "Women's Rights",
        "title_hi": "महिला अधिकार",
        "description": "Legal protections for women against harassment, violence, and discrimination",
        "icon": "👩",
        "acts": ["IPC", "CPA", "CONSTITUTION", "FAMILY"],
    },
    "labour": {
        "title": "Labour & Employment",
        "title_hi": "श्रम अधिकार",
        "description": "Worker rights, wages, workplace safety, and employment protections",
        "icon": "👷",
        "acts": ["LABOUR"],
    },
    "property": {
        "title": "Property & Real Estate",
        "title_hi": "संपत्ति अधिकार",
        "description": "Land, housing, property ownership, and RERA protections",
        "icon": "🏠",
        "acts": ["IPC", "CONSTITUTION", "RERA"],
    },
    "family": {
        "title": "Family & Marriage",
        "title_hi": "परिवार कानून",
        "description": "Marriage, divorce, maintenance, custody, and domestic violence",
        "icon": "👪",
        "acts": ["FAMILY"],
    },
    "child_protection": {
        "title": "Child Protection",
        "title_hi": "बाल संरक्षण",
        "description": "Protection of children from abuse, exploitation, and trafficking",
        "icon": "🧒",
        "acts": ["POCSO"],
    },
    "rti": {
        "title": "Right to Information",
        "title_hi": "सूचना का अधिकार",
        "description": "Access government information for transparency and accountability",
        "icon": "📋",
        "acts": ["RTI"],
    },
    "traffic": {
        "title": "Traffic & Motor Vehicles",
        "title_hi": "यातायात कानून",
        "description": "Road safety, traffic violations, accident claims, and vehicle insurance",
        "icon": "🚗",
        "acts": ["MVA"],
    },
    "discrimination": {
        "title": "Anti-Discrimination",
        "title_hi": "भेदभाव विरोधी",
        "description": "Protection against caste, gender, and social discrimination",
        "icon": "✊",
        "acts": ["SCST", "CONSTITUTION"],
    },
    "financial": {
        "title": "Financial & Banking",
        "title_hi": "वित्तीय अधिकार",
        "description": "Cheque bounce, banking disputes, and financial fraud protections",
        "icon": "💰",
        "acts": ["NIA"],
    },
    "drugs": {
        "title": "Narcotics & Substances",
        "title_hi": "मादक द्रव्य कानून",
        "description": "Drug offences, penalties, bail provisions under NDPS Act",
        "icon": "⚠️",
        "acts": ["NDPS"],
    },
    "dispute_resolution": {
        "title": "Dispute Resolution",
        "title_hi": "विवाद समाधान",
        "description": "Arbitration, mediation, and alternative dispute resolution",
        "icon": "🤝",
        "acts": ["ARBA"],
    },
}


@router.get("/categories")
async def list_categories():
    """List all rights categories."""
    return [
        {"id": cat_id, **cat_info}
        for cat_id, cat_info in RIGHTS_CATEGORIES.items()
    ]


@router.get("/category/{category_id}")
async def get_rights_by_category(category_id: str):
    """Get all rights/sections for a specific category."""
    if category_id not in RIGHTS_CATEGORIES:
        return {"error": "Category not found", "available": list(RIGHTS_CATEGORIES.keys())}

    cat = RIGHTS_CATEGORIES[category_id]
    sections = []
    for act_short in cat.get("acts", []):
        sections.extend(retrieval.search_by_act(act_short))

    return {
        "category": cat,
        "sections": [
            {
                "id": s.id,
                "act": s.act,
                "section_number": s.section_number,
                "title": s.title,
                "simplified": s.simplified,
                "text": s.text,
                "category": s.category,
            }
            for s in sections
        ],
        "total": len(sections),
    }


@router.get("/search")
async def search_rights(q: str = Query(..., min_length=2)):
    """Search for specific rights across all categories."""
    results = retrieval.search(q, top_k=10)
    return {
        "query": q,
        "results": [
            {
                "id": section.id,
                "act": section.act,
                "short_name": section.short_name,
                "section_number": section.section_number,
                "title": section.title,
                "simplified": section.simplified,
                "score": round(score, 4),
            }
            for section, score in results
        ],
    }
