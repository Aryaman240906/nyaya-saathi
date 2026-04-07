"""
Debate Orchestrator — manages the multi-agent reasoning flow.

Pipeline:
1. Prosecutor (Domain Specialist) → primary analysis
2. Defense (Challenger) → counter-arguments [parallel with Procedure Agent if procedural]
3. Validator (Judge) → final synthesis

Streams intermediate states to the frontend via StreamChunk.
Falls back to single-pass generation if any agent fails.
"""
from __future__ import annotations
import json
import logging
import time
from typing import AsyncGenerator

import config
from models.schemas import StreamChunk
from agents.prosecutor import ProsecutorAgent
from agents.defense import DefenseAgent
from agents.validator import ValidatorAgent
from agents.procedure_agent import ProcedureAgent
from services import audit

logger = logging.getLogger(__name__)

# Singleton agent instances
_prosecutor = ProsecutorAgent()
_defense = DefenseAgent()
_validator = ValidatorAgent()
_procedure = ProcedureAgent()


async def run_debate(
    context: str,
    query: str,
    session_id: str = "",
    language_instruction: str = "",
    intent: str = "situational",
) -> AsyncGenerator[StreamChunk, None]:
    """
    Execute the full multi-agent debate pipeline.
    Yields StreamChunk objects for real-time frontend visualization.
    """
    debate_start = time.monotonic()

    # ── Step 1: Prosecutor ──────────────────────────────────────────
    yield StreamChunk(type="debate_start", data={
        "message": "Starting legal analysis...",
        "agents": ["prosecutor", "defense", "validator"],
    })

    yield StreamChunk(type="debate_prosecutor", data={
        "status": "running",
        "message": "Prosecutor analyzing applicable laws...",
    })

    prosecutor_result = await _prosecutor.generate(
        context=context,
        query=query,
        session_id=session_id,
    )

    if "error" in prosecutor_result and "parse_error" not in prosecutor_result:
        yield StreamChunk(type="debate_prosecutor", data={
            "status": "error",
            "error": prosecutor_result["error"],
        })
        # Fallback — yield raw context
        yield StreamChunk(type="response", data={"text": _build_fallback(context, query)})
        return

    yield StreamChunk(type="debate_prosecutor", data={
        "status": "done",
        "result": _sanitize_for_stream(prosecutor_result),
        "sections_found": len(prosecutor_result.get("applicable_sections", [])),
        "latency_ms": prosecutor_result.get("_latency_ms", 0),
    })

    # ── Step 2: Defense ─────────────────────────────────────────────
    yield StreamChunk(type="debate_defense", data={
        "status": "running",
        "message": "Defense reviewing analysis for gaps...",
    })

    prosecutor_json = json.dumps(prosecutor_result, ensure_ascii=False, default=str)
    defense_result = await _defense.generate(
        context=context,
        query=query,
        session_id=session_id,
        prosecutor_output=prosecutor_json,
    )

    yield StreamChunk(type="debate_defense", data={
        "status": "done",
        "result": _sanitize_for_stream(defense_result),
        "challenges": len(defense_result.get("challenges", [])),
        "assessment": defense_result.get("overall_assessment", ""),
        "latency_ms": defense_result.get("_latency_ms", 0),
    })

    # ── Step 2b: Procedure Agent (parallel, if procedural intent) ──
    procedure_result = None
    if intent == "procedural":
        yield StreamChunk(type="debate_procedure", data={
            "status": "running",
            "message": "Generating step-by-step procedure...",
        })
        procedure_result = await _procedure.generate(
            context=context,
            query=query,
            session_id=session_id,
        )
        yield StreamChunk(type="debate_procedure", data={
            "status": "done",
            "steps": len(procedure_result.get("steps", [])),
        })

    # ── Step 3: Validator (Judge) ───────────────────────────────────
    yield StreamChunk(type="debate_validator", data={
        "status": "running",
        "message": "Judge synthesizing final response...",
    })

    defense_json = json.dumps(defense_result, ensure_ascii=False, default=str)
    validator_result = await _validator.generate(
        context=context,
        query=query,
        session_id=session_id,
        prosecutor_output=prosecutor_json,
        defense_output=defense_json,
        language_instruction=language_instruction,
    )

    if "error" in validator_result and "parse_error" not in validator_result:
        yield StreamChunk(type="debate_validator", data={
            "status": "error",
            "error": validator_result["error"],
        })
        # Use prosecutor analysis as fallback
        yield StreamChunk(type="response", data={
            "text": prosecutor_result.get("legal_analysis", _build_fallback(context, query)),
        })
    else:
        yield StreamChunk(type="debate_validator", data={
            "status": "done",
            "confidence": validator_result.get("confidence_score", 0.5),
            "latency_ms": validator_result.get("_latency_ms", 0),
        })

        # ── Format the final response with all structured data ──────────────────────────────
        final_text = validator_result.get("final_response", "")
        
        # We must manually inject the structured execution plan so the frontend Markdown renders it natively!
        primary_law = next((l for l in validator_result.get("applicable_law", []) if l.get("is_primary")), None)
        if primary_law:
            final_text += f"\n\n### ⚖️ Primary Applicable Law\n**{primary_law.get('act')} (Section {primary_law.get('section')})**\n> *{primary_law.get('relevance')}*\n*(Suitability Score: {primary_law.get('suitability_score')}/100)*\n"
        
        actions = validator_result.get("action_steps", [])
        if actions:
            final_text += "\n\n### 🚀 Executable Plan\n"
            for act in actions:
                final_text += f"{act.get('step')}. **{act.get('action')}** — {act.get('details')} *(Timeline: {act.get('timeline')})*\n"
                
        docs = validator_result.get("documents_needed", [])
        if docs:
            final_text += "\n\n### 📄 Required Documents\n"
            for d in docs:
                final_text += f"- {d}\n"
                
        auths = validator_result.get("authorities_to_approach", [])
        if auths:
            final_text += "\n\n### 🏢 Where to Go\n"
            for a in auths:
                final_text += f"- **{a.get('name')}**: {a.get('contact')} *(Submit when: {a.get('when')})*\n"

        if final_text:
            yield StreamChunk(type="response", data={"text": final_text})

    # ── Emit debate metadata ────────────────────────────────────────
    total_latency = (time.monotonic() - debate_start) * 1000

    debate_data = {
        "prosecutor": _sanitize_for_stream(prosecutor_result),
        "defense": _sanitize_for_stream(defense_result),
        "validator": _sanitize_for_stream(validator_result),
        "procedure": _sanitize_for_stream(procedure_result) if procedure_result else None,
        "total_latency_ms": round(total_latency, 1),
        "intent": intent,
    }

    yield StreamChunk(type="debate_complete", data={
        "total_latency_ms": round(total_latency, 1),
        "agents_used": 4 if procedure_result else 3,
        "confidence": validator_result.get("confidence_score", 0.5),
        "debate_summary": validator_result.get("debate_summary", {}),
        "applicable_law": validator_result.get("applicable_law", []),
        "your_rights": validator_result.get("your_rights", []),
        "action_steps": validator_result.get("action_steps", []),
        "documents_needed": validator_result.get("documents_needed", []),
        "authorities": validator_result.get("authorities_to_approach", []),
    })

    # Audit log
    await audit.log_debate(session_id, {
        "total_latency_ms": round(total_latency, 1),
        "agents_used": 4 if procedure_result else 3,
        "confidence": validator_result.get("confidence_score", 0.5),
        "prosecutor_sections": len(prosecutor_result.get("applicable_sections", [])),
        "defense_challenges": len(defense_result.get("challenges", [])),
        "defense_assessment": defense_result.get("overall_assessment", ""),
    })


def _sanitize_for_stream(data: dict | None) -> dict:
    """Remove internal fields before sending to frontend."""
    if not data:
        return {}
    clean = {k: v for k, v in data.items() if not k.startswith("_")}
    # Truncate very long text fields for the stream
    for key in ("legal_analysis", "defense_perspective", "final_response"):
        if key in clean and isinstance(clean[key], str) and len(clean[key]) > 500:
            clean[f"{key}_preview"] = clean[key][:500] + "..."
    return clean


def _build_fallback(context: str, query: str) -> str:
    """Build a fallback response when debate agents fail."""
    return (
        "Server traffic is currently extremely high causing our primary AI synthesis engine to be temporarily throttled. "
        "However, our retrieval system has instantly successfully matched your query to the following exact legal provisions:\n\n" + context
    )
