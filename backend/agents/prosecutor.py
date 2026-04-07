"""
Prosecutor Agent — Domain Specialist.

The primary legal analysis agent that:
- Identifies applicable laws from retrieved context
- Extracts relevant rights and procedures
- Provides the initial legal assessment
- Must be strictly grounded in retrieved sections only
"""
from __future__ import annotations
from agents.base import BaseAgent


class ProsecutorAgent(BaseAgent):
    name = "prosecutor"

    def get_system_prompt(self) -> str:
        return """You are the PROSECUTOR AGENT in a legal reasoning debate system for Indian law.

## Your Role
You are the Domain Specialist — your job is to provide the PRIMARY legal analysis based strictly on the retrieved legal context.

## Rules
1. ONLY cite laws and sections present in the RETRIEVED CONTEXT.
2. NEVER fabricate legal sections, articles, or provisions.
3. Be thorough — identify ALL applicable sections, not just the most obvious one.
4. Consider both the literal text and simplified explanation of each section.
5. If sections from multiple acts apply, reference all of them.

## Output Format (JSON)
You MUST respond with valid JSON matching this exact structure:
{
    "applicable_sections": [
        {
            "act": "Act name",
            "section": "Section number",
            "title": "Section title",
            "relevance": "Why this section applies to the query",
            "punishment": "Punishment if applicable"
        }
    ],
    "legal_analysis": "Detailed analysis of how the law applies to this situation",
    "rights_identified": ["Right 1", "Right 2"],
    "recommended_actions": ["Action 1", "Action 2"],
    "urgency_assessment": "low|medium|high|critical",
    "confidence_notes": "Any caveats or areas where the analysis might be incomplete"
}"""

    def format_input(self, context: str, query: str, **kwargs) -> str:
        return f"""## Retrieved Legal Context
{context}

## Citizen's Query
{query}

## Instructions
Analyze this query using ONLY the retrieved legal context above. Identify all applicable sections, rights, and recommended actions. Output valid JSON."""

    def parse_output(self, raw_text: str) -> dict:
        parsed = self._safe_json_parse(raw_text)
        # Ensure required fields
        parsed.setdefault("applicable_sections", [])
        parsed.setdefault("legal_analysis", "")
        parsed.setdefault("rights_identified", [])
        parsed.setdefault("recommended_actions", [])
        parsed.setdefault("urgency_assessment", "low")
        parsed.setdefault("confidence_notes", "")
        return parsed
