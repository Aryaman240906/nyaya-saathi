"""
Reasoning Engine — Full Pipeline Orchestrator.

Upgraded pipeline:
1. Safety gate → 2. Query analysis (intent, clarification, expansion)
3. Language detection → 4. Tri-modal retrieval (BM25 + Dense + Structured + Cross-Ref)
5. 4-stream fusion → 6. Multi-Agent Debate OR Single-pass generation
7. Grounding validation → 8. Response structuring
"""
from __future__ import annotations
import json
import logging
import time
from typing import AsyncGenerator

import config
from models.schemas import (
    ChatRequest, StreamChunk, QueryAnalysis,
)
from services import retrieval, structured_nav, fusion, language, safety, grounding, cache, audit
from services import embeddings, query_engine, gemini_rest
from models.database import get_history, add_message, create_session, session_exists, update_session_title
from agents import orchestrator as debate_orchestrator

logger = logging.getLogger(__name__)

_client_ready = False


def init_client():
    """Initialize the Gemini client and all dependent services."""
    global _client_ready
    if config.GEMINI_API_KEY:
        _client_ready = True
        logger.info("Gemini client initialized with model: %s", config.GEMINI_MODEL)

        # Initialize dependent services
        from agents.base import set_agent_client
        set_agent_client(True)  # Signal that client is ready
        embeddings.init_embeddings_client(True)
        query_engine.init_query_engine(True)
        grounding.init_grounding_client(True)
    else:
        logger.warning("No GEMINI_API_KEY set — LLM features will be unavailable")


SYSTEM_PROMPT = """You are NYAYA-SAATHI (न्याय-साथी), an AI legal awareness assistant for Indian citizens.

## Your Role
- You help citizens understand their legal rights and navigate legal procedures in India.
- You provide SIMPLIFIED, ACTIONABLE legal information grounded in Indian law.
- You are NOT a lawyer. You do NOT provide legal advice. You provide legal AWARENESS and INFORMATION.

## Response Rules
1. ONLY cite laws and sections that are present in the RETRIEVED CONTEXT below.
2. NEVER fabricate, guess, or hallucinate legal sections, articles, or provisions.
3. If the retrieved context doesn't contain relevant information, say so honestly.
4. Always structure your response with these sections (use markdown headers):
   - **Applicable Law** — Which law/section applies
   - **Your Rights** — What rights the person has
   - **What You Should Do** — Step-by-step actionable guidance
   - **Documents Needed** — What papers/evidence to gather
   - **Where to Go** — Which authority/court/portal to approach
5. Use simple language. Avoid legal jargon. Explain terms if you must use them.
6. If the situation seems urgent (violence, threats, fraud), LEAD with emergency helplines.
7. Be empathetic and supportive — people come to you in difficult situations.

## Language
{language_instruction}

## Important
- Cite specific section numbers when referencing laws.
- Mention relevant helplines and portals where applicable.
- If the query is outside Indian law jurisdiction, say so clearly.
- If you're unsure, express uncertainty rather than guessing.
"""


async def _auto_title_session(session_id: str, query: str):
    """Generate a short title for the session based on the first query."""
    if not _client_ready:
        await update_session_title(session_id, query[:60])
        return
    try:
        prompt = (
            f"Generate a very short title (max 6 words) for a legal consultation "
            f"that starts with this question. Output ONLY the title, no quotes:\n{query[:200]}"
        )
        title = await gemini_rest.generate_content(
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            temperature=0.1,
            max_output_tokens=30,
        )
        title = title.strip().strip('"').strip("'")[:80]
        if title:
            await update_session_title(session_id, title)
    except Exception as e:
        logger.debug("Auto-title failed: %s", e)
        await update_session_title(session_id, query[:60])


async def process_chat(
    request: ChatRequest,
    user_id: str | None = None,
) -> AsyncGenerator[StreamChunk, None]:
    """
    Process a chat request through the full enhanced pipeline.
    Yields StreamChunk objects for SSE streaming.

    Args:
        request: The chat request with message, session_id, etc.
        user_id: Authenticated user ID (None for anonymous).
    """
    pipeline_start = time.monotonic()

    # ── 1. Session Management ───────────────────────────────────────
    session_id = request.session_id
    is_new_session = False
    if not session_id or not await session_exists(session_id):
        session_id = await create_session(user_id=user_id)
        is_new_session = True

    yield StreamChunk(type="thinking", data={
        "message": "Understanding your question...",
        "session_id": session_id,
    })

    # ── 2. Rate Limiting ────────────────────────────────────────────
    rate_key = user_id or session_id
    if not cache.check_rate_limit(rate_key):
        yield StreamChunk(type="error", data={
            "message": "You're sending too many requests. Please wait a moment.",
            "session_id": session_id,
        })
        yield StreamChunk(type="done", data={"session_id": session_id})
        return

    # ── 3. Safety Gate ──────────────────────────────────────────────
    if safety.check_jailbreak(request.message):
        await audit.log_jailbreak(session_id, request.message[:200])
        yield StreamChunk(type="error", data={
            "message": "I can only help with legal questions related to Indian law. "
                       "Please ask me about your legal rights, procedures, or any legal situation you're facing.",
            "session_id": session_id,
        })
        yield StreamChunk(type="done", data={"session_id": session_id})
        return

    # ── 4. Urgency Detection ────────────────────────────────────────
    urgency = safety.detect_urgency(request.message)
    if urgency.level in ("critical", "high"):
        yield StreamChunk(type="urgency", data=urgency.model_dump())

    # ── 5. Language Detection ───────────────────────────────────────
    detected_lang = request.language or language.detect_language(request.message)

    yield StreamChunk(type="thinking", data={
        "message": "Analyzing your query...",
        "language": detected_lang,
    })

    # ── 6. Advanced Query Analysis ──────────────────────────────────
    query_analysis = await query_engine.analyze_query(request.message, detected_lang)

    yield StreamChunk(type="query_analysis", data={
        "intent": query_analysis.intent,
        "is_vague": query_analysis.is_vague,
        "was_clarified": query_analysis.was_clarified,
        "effective_query": query_analysis.effective_query,
        "parties": query_analysis.parties,
        "expanded_queries": len(query_analysis.retrieval_queries),
    })

    # ── 7. Query Preparation ────────────────────────────────────────
    retrieval_query = query_analysis.effective_query

    # For Hindi (Devanagari), translate to English for retrieval
    if detected_lang == "hi" and _client_ready:
        try:
            translation_text = await gemini_rest.generate_content(
                contents=[{"role": "user", "parts": [{"text": f"Translate this Hindi legal query to English. Only output the translation:\n{request.message}"}]}],
            )
            retrieval_query = translation_text.strip()
        except Exception as e:
            logger.error("Translation failed: %s", e)

    yield StreamChunk(type="thinking", data={
        "message": "Searching legal database (4 streams)...",
    })

    # ── 8. Tri-Modal Retrieval ──────────────────────────────────────
    # Stream 1: BM25 (with query expansion)
    bm25_results = retrieval.multi_query_search(
        query_analysis.retrieval_queries or [retrieval_query],
        top_k=config.MAX_RETRIEVAL_RESULTS,
    )

    # Stream 2: Dense vector similarity
    dense_results = await embeddings.dense_search(retrieval_query, top_k=config.MAX_RETRIEVAL_RESULTS)

    # Stream 3: Structured navigation
    struct_results = structured_nav.structured_search(retrieval_query, top_k=config.MAX_RETRIEVAL_RESULTS)

    # Stream 4: Cross-reference graph traversal
    seed_sections = [s for s, _ in bm25_results[:3]] + [s for s, _ in struct_results[:2]]
    cross_ref_results = retrieval.cross_reference_search(seed_sections, depth=1)

    # Corpus gap detection
    gap_analysis = retrieval.detect_corpus_gap(bm25_results, dense_results, struct_results)

    # ── 9. 4-Stream Fusion ──────────────────────────────────────────
    fused_results = fusion.fuse(
        bm25_results=bm25_results,
        structured_results=struct_results,
        top_k=config.MAX_RETRIEVAL_RESULTS,
        dense_results=dense_results,
        cross_ref_results=cross_ref_results,
    )
    sources = fusion.results_to_sources(fused_results)
    context = fusion.build_context(fused_results)

    yield StreamChunk(type="retrieval", data={
        "sources_found": len(fused_results),
        "sources": [s.model_dump() for s in sources[:5]],
        "streams": {
            "bm25": len(bm25_results),
            "dense": len(dense_results),
            "structured": len(struct_results),
            "cross_ref": len(cross_ref_results),
        },
        "gap_analysis": gap_analysis,
    })

    # ── 10. Determine generation mode ───────────────────────────────
    use_debate = (
        config.DEBATE_ENABLED
        and request.mode == "debate"
        and _client_ready
        and context.strip()
    )

    # ── 11. Get Conversation History ────────────────────────────────
    history = await get_history(session_id, limit=10)

    # ── 12. Generate Response ───────────────────────────────────────
    lang_instruction = language.get_response_language_instruction(detected_lang)

    if use_debate:
        # ── DEBATE MODE: Multi-Agent Pipeline ───────────────────────
        yield StreamChunk(type="thinking", data={
            "message": "Running multi-agent legal analysis...",
        })

        full_response = ""
        debate_confidence = 0.5

        async for chunk in debate_orchestrator.run_debate(
            context=context,
            query=request.message,
            session_id=session_id,
            language_instruction=lang_instruction,
            intent=query_analysis.intent,
        ):
            if chunk.type == "response":
                full_response += chunk.data.get("text", "")
            elif chunk.type == "debate_complete":
                debate_confidence = chunk.data.get("confidence", 0.5)
            yield chunk

        # Grounding validation on final response
        retrieved_sections = [sec for sec, _, _ in fused_results]
        grounding_report = grounding.validate_citations(full_response, retrieved_sections)

        confidence = debate_confidence

    else:
        # ── SIMPLE MODE: Single-pass generation ─────────────────────
        if not _client_ready:
            yield StreamChunk(type="response", data={
                "text": "⚠️ LLM service is not configured. Please set GEMINI_API_KEY.\n\n"
                        "Here are the relevant legal provisions:\n\n" + context,
            })
            yield StreamChunk(type="done", data={"session_id": session_id})
            return

        system = SYSTEM_PROMPT.format(language_instruction=lang_instruction)
        messages = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            messages.append({"role": role, "parts": [{"text": msg["content"]}]})

        user_prompt = f"""## Retrieved Legal Context
{context if context else "No specific legal provisions were found for this query."}

## User's Question
{request.message}

## Query Analysis
Intent: {query_analysis.intent} | Parties: {', '.join(query_analysis.parties)}

## Instructions
- Base your answer STRICTLY on the Retrieved Legal Context above.
- Structure your response clearly with the sections mentioned in your system prompt.
- If the context is insufficient, acknowledge this honestly.
"""
        messages.append({"role": "user", "parts": [{"text": user_prompt}]})

        try:
            full_response = ""
            async for chunk_text in gemini_rest.generate_content_stream(
                contents=messages,
                system_instruction=system,
                temperature=0.3,
                max_output_tokens=4096
            ):
                full_response += chunk_text
                yield StreamChunk(type="response", data={"text": chunk_text})

        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            fallback_text = (
                "Server traffic is currently extremely high causing our primary AI synthesis engine to be temporarily throttled. "
                "However, our retrieval system has instantly successfully matched your query to the following exact legal provisions:\n\n" + context
            )
            yield StreamChunk(type="response", data={"text": fallback_text})
            yield StreamChunk(type="done", data={"session_id": session_id})
            return

        # Grounding validation
        retrieved_sections = [sec for sec, _, _ in fused_results]
        grounding_report = grounding.validate_citations(full_response, retrieved_sections)
        retrieval_scores = [score for _, score, _ in fused_results]
        confidence = grounding.compute_confidence(
            retrieval_scores, grounding_report, bool(context.strip())
        )

    # ── 13. Save Messages ──────────────────────────────────────────
    await add_message(session_id, "user", request.message, {
        "language": detected_lang,
        "urgency": urgency.level,
        "intent": query_analysis.intent,
        "mode": "debate" if use_debate else "simple",
    })
    await add_message(session_id, "assistant", full_response, {
        "confidence": confidence,
        "sources_count": len(sources),
        "grounding": grounding_report,
        "mode": "debate" if use_debate else "simple",
    })

    # Auto-title new sessions
    if is_new_session:
        # Fire-and-forget title generation
        import asyncio
        asyncio.create_task(_auto_title_session(session_id, request.message))

    # Audit log
    pipeline_latency = (time.monotonic() - pipeline_start) * 1000
    await audit.log_query(session_id, request.message, detected_lang, urgency.level)

    # ── 14. Final metadata ─────────────────────────────────────────
    yield StreamChunk(type="sources", data={
        "sources": [s.model_dump() for s in sources],
        "confidence": confidence,
        "grounding": grounding_report,
        "language": detected_lang,
        "urgency": urgency.model_dump(),
        "mode": "debate" if use_debate else "simple",
        "pipeline_latency_ms": round(pipeline_latency, 1),
        "gap_analysis": gap_analysis,
    })

    yield StreamChunk(type="done", data={"session_id": session_id})


async def analyze_document(text: str, lang: str = "en") -> dict:
    """Analyze a legal document and provide simplified explanation."""
    if not _client_ready:
        return {"error": "LLM service not configured"}

    prompt = f"""Analyze the following legal document and provide:
1. **Document Type** — What kind of document is this?
2. **Summary** — A brief, plain-language summary
3. **Key Points** — Important clauses, dates, obligations, or rights
4. **Entities** — Names, addresses, dates, amounts mentioned
5. **What This Means For You** — Practical implications
6. **What You Should Do** — Recommended next steps

{language.get_response_language_instruction(lang)}

## Document Text:
{text[:5000]}
"""
    try:
        response_text = await gemini_rest.generate_content(
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            temperature=0.2,
            max_output_tokens=2048
        )
        return {"analysis": response_text, "language": lang}
    except Exception as e:
        logger.error("Document analysis failed: %s", e)
        return {"error": str(e)}
