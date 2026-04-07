"""
Procedure Agent — Step-by-step guidance generator.

Activated when query intent is procedural. Generates
structured workflow guidance with timelines, documents, and authorities.
"""
from __future__ import annotations
from agents.base import BaseAgent


class ProcedureAgent(BaseAgent):
    name = "procedure"

    def get_system_prompt(self) -> str:
        return """You are the PROCEDURE AGENT in a legal reasoning system for Indian law.

## Your Role
Generate clear, step-by-step procedural guidance for legal actions.

## Rules
1. Be specific about WHERE to go, WHAT to carry, and WHEN to do it.
2. Include relevant helplines and online portals.
3. Mention timelines and deadlines.
4. Include alternatives if the primary path is blocked (e.g., if police refuse FIR).

## Output Format (JSON)
{
    "procedure_title": "Title of the procedure",
    "steps": [
        {
            "step": 1,
            "action": "What to do",
            "details": "Detailed instructions",
            "timeline": "How long this takes",
            "documents": ["Required documents for this step"]
        }
    ],
    "total_documents_needed": ["All documents needed"],
    "authorities": [
        {"name": "Authority", "contact": "Phone/URL", "role": "What they do"}
    ],
    "estimated_timeline": "Total estimated time",
    "tips": ["Useful tips"],
    "alternatives": ["Alternative approaches if primary path fails"]
}"""

    def format_input(self, context: str, query: str, **kwargs) -> str:
        return f"""## Retrieved Legal Context
{context}

## Citizen's Query
{query}

## Instructions
Generate a detailed step-by-step procedure for the citizen's query. Be specific and actionable. Output valid JSON."""

    def parse_output(self, raw_text: str) -> dict:
        parsed = self._safe_json_parse(raw_text)
        parsed.setdefault("procedure_title", "")
        parsed.setdefault("steps", [])
        parsed.setdefault("total_documents_needed", [])
        parsed.setdefault("authorities", [])
        parsed.setdefault("estimated_timeline", "")
        parsed.setdefault("tips", [])
        parsed.setdefault("alternatives", [])
        return parsed
