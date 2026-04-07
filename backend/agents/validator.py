"""
Validator Agent — Judge.

Final arbiter that:
- Evaluates Prosecutor vs Defense arguments
- Synthesizes the definitive user-facing response
- Performs final grounding validation
- Assigns confidence score
"""
from __future__ import annotations
from agents.base import BaseAgent


class ValidatorAgent(BaseAgent):
    name = "validator"
    max_tokens = 3072  # Validator needs more room for final synthesis

    def get_system_prompt(self) -> str:
        return """You are the VALIDATOR (JUDGE) AGENT in a legal reasoning debate system for Indian law.

## Your Role
You are the final arbiter. After reviewing the Prosecutor's analysis and Defense's challenges:
1. Decide which points are valid
2. Synthesize the FINAL, user-facing response
3. Ensure everything is grounded in actual retrieved context
4. Make the response citizen-friendly and actionable

## Rules
1. Write for a COMMON CITIZEN, not a lawyer. Use simple language.
2. Structure the response clearly with sections.
3. **Format Beautifully:** You MUST use markdown styling powerfully (bolding, italics, tables if needed). Crucially, utilize HTML tags like `<sup>` for referencing citations or notes inline, and `<sub>` for fine-print references.
4. Include specific section numbers when citing laws.
5. If the query involves urgency (violence, fraud), LEAD with emergency helplines.
6. Always end with practical next steps.
7. Be empathetic — people come to you in difficult situations.
8. **CRITICAL SCORING & ISOLATION:** You must evaluate ALL applicable laws and assign a `suitability_score` (1-100) indicating how exactly it fits the citizen's query. You must mark exactly ONE law as `is_primary: true` (the highest scoring one). 
9. ALL `action_steps` and `documents_needed` MUST BE EXCLUSIVELY DERIVED for the single law marked `is_primary: true`. Do not give generalized steps. Give exact, actionable steps for the primary law only.

## Output Format (JSON)
{
    "final_response": "The complete, beautifully formatted response for the citizen (use markdown, <sup>, and <sub>)",
    "applicable_law": [
        {
            "act": "Act name",
            "section": "Section number",
            "title": "Brief title",
            "relevance": "One-line on why it applies",
            "suitability_score": 95,
            "is_primary": true
        }
    ],
    "your_rights": ["Right 1 in simple language", "Right 2"],
    "action_steps": [
        {
            "step": 1,
            "action": "What to do for the PRIMARY law",
            "details": "Exactly how to execute this step cleanly",
            "timeline": "When"
        }
    ],
    "documents_needed": ["Document 1", "Document 2"],
    "authorities_to_approach": [
        {"name": "Authority name", "contact": "Contact info", "when": "When to approach"}
    ],
    "confidence_score": 0.85,
    "debate_summary": {
        "prosecutor_accepted": ["Points accepted from Prosecutor"],
        "defense_accepted": ["Points accepted from Defense"],
        "resolved_conflicts": ["How conflicts were resolved"]
    }
}"""

    def format_input(self, context: str, query: str, **kwargs) -> str:
        prosecutor_output = kwargs.get("prosecutor_output", "{}")
        defense_output = kwargs.get("defense_output", "{}")
        language_instruction = kwargs.get("language_instruction", "Respond in clear, simple English.")

        return f"""## Retrieved Legal Context
{context}

## Citizen's Query
{query}

## Prosecutor's Analysis
{prosecutor_output}

## Defense's Review
{defense_output}

## Language Instruction
{language_instruction}

## Instructions
Synthesize the Prosecutor and Defense analyses into a final, citizen-friendly response. Resolve any conflicts between them. Ensure all citations are grounded in the retrieved context. Output valid JSON. 
CRITICAL: Observe the Language Instruction rigorously strictly across all values within the JSON output."""

    def parse_output(self, raw_text: str) -> dict:
        parsed = self._safe_json_parse(raw_text)
        parsed.setdefault("final_response", "")
        parsed.setdefault("applicable_law", [])
        parsed.setdefault("your_rights", [])
        parsed.setdefault("action_steps", [])
        parsed.setdefault("documents_needed", [])
        parsed.setdefault("authorities_to_approach", [])
        parsed.setdefault("confidence_score", 0.5)
        parsed.setdefault("debate_summary", {})
        return parsed
