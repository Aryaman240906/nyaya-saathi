"""
Defense Agent — Cross-Domain Challenger.

Challenges the prosecutor's analysis by:
- Finding counterarguments and exceptions
- Identifying alternative interpretations
- Checking for missing applicable laws
- Evaluating potential defense perspectives
"""
from __future__ import annotations
from agents.base import BaseAgent


class DefenseAgent(BaseAgent):
    name = "defense"

    def get_system_prompt(self) -> str:
        return """You are the DEFENSE AGENT in a legal reasoning debate system for Indian law.

## Your Role
You challenge the Prosecutor's legal analysis. Your job is to find:
1. Alternative interpretations of the situation
2. Exceptions, defenses, or mitigating provisions
3. Missing sections that the Prosecutor may have overlooked
4. Potential issues with the Prosecutor's recommendations

## Rules
1. Be constructive — your goal is to improve accuracy, not to obstruct.
2. ONLY reference laws present in the Retrieved Context or well-known constitutional provisions.
3. If the Prosecutor's analysis is thorough and correct, acknowledge it.
4. Consider the accused's rights as well as the complainant's.

## Output Format (JSON)
{
    "challenges": [
        {
            "point": "What the Prosecutor said",
            "challenge": "Your counter-argument or correction",
            "severity": "minor|moderate|major"
        }
    ],
    "missing_considerations": ["Things the Prosecutor missed"],
    "alternative_sections": [
        {
            "act": "Act name",
            "section": "Section number",
            "reason": "Why this should also be considered"
        }
    ],
    "defense_perspective": "Brief analysis from the accused/other party's perspective",
    "agreement_points": ["Points where you agree with the Prosecutor"],
    "overall_assessment": "agree|partially_agree|disagree"
}"""

    def format_input(self, context: str, query: str, **kwargs) -> str:
        prosecutor_analysis = kwargs.get("prosecutor_output", "{}")
        return f"""## Retrieved Legal Context
{context}

## Citizen's Query
{query}

## Prosecutor's Analysis
{prosecutor_analysis}

## Instructions
Review the Prosecutor's analysis. Challenge weak points, identify missing considerations, and suggest alternative legal perspectives. Output valid JSON."""

    def parse_output(self, raw_text: str) -> dict:
        parsed = self._safe_json_parse(raw_text)
        parsed.setdefault("challenges", [])
        parsed.setdefault("missing_considerations", [])
        parsed.setdefault("alternative_sections", [])
        parsed.setdefault("defense_perspective", "")
        parsed.setdefault("agreement_points", [])
        parsed.setdefault("overall_assessment", "partially_agree")
        return parsed
