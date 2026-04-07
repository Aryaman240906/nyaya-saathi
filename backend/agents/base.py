"""
Base Agent — Abstract foundation for all debate agents.

Every agent:
- Receives legal context + query
- Generates structured Pydantic output (never free-text)
- Has token budget management
- Shares a Gemini client reference
"""
from __future__ import annotations
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from services import audit, gemini_rest
import config

logger = logging.getLogger(__name__)

_client_ready = False


def set_agent_client(ready: bool):
    """Set the shared Gemini client for all agents."""
    global _client_ready
    _client_ready = ready


def get_client() -> bool:
    return _client_ready


class BaseAgent(ABC):
    """Abstract base for all debate agents."""

    name: str = "base"
    temperature: float = 0.2
    max_tokens: int = 2048

    def __init__(self):
        self.temperature = config.DEBATE_TEMPERATURE
        self.max_tokens = config.DEBATE_MAX_TOKENS_PER_AGENT

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the agent's system prompt."""
        ...

    @abstractmethod
    def format_input(self, context: str, query: str, **kwargs) -> str:
        """Format the input prompt for this agent."""
        ...

    @abstractmethod
    def parse_output(self, raw_text: str) -> dict:
        """Parse the raw LLM output into structured data."""
        ...

    async def generate(self, context: str, query: str, session_id: str = "", **kwargs) -> dict:
        """
        Generate a structured response from this agent.
        Returns parsed dict conforming to agent's schema.
        """
        if not get_client():
            return {"error": "LLM client not available", "agent": self.name}

        system = self.get_system_prompt()
        user_input = self.format_input(context, query, **kwargs)

        start = time.monotonic()
        try:
            raw = await gemini_rest.generate_content(
                contents=[{"role": "user", "parts": [{"text": user_input}]}],
                system_instruction=system,
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
                response_mime_type="application/json"
            )

            latency = (time.monotonic() - start) * 1000

            # Log the LLM call
            await audit.log_llm_call(
                session_id=session_id,
                model=config.GEMINI_MODEL,
                agent=self.name,
                latency_ms=latency,
            )

            # Parse structured output
            parsed = self.parse_output(raw)
            parsed["_agent"] = self.name
            parsed["_latency_ms"] = round(latency, 1)
            return parsed

        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            logger.error("Agent %s failed (%.0fms): %s", self.name, latency, e)
            return {
                "error": str(e),
                "agent": self.name,
                "_latency_ms": round(latency, 1),
            }

    def _safe_json_parse(self, text: str) -> dict:
        """Safely parse JSON from LLM output, handling common issues."""
        text = text.strip()
        # Remove markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from text
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.warning("Agent %s: Could not parse JSON output", self.name)
            return {"raw_text": text, "parse_error": True}
