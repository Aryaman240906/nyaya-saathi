"""
Reasoning Engine — Full Pipeline Orchestrator.

Upgraded pipeline (v4 — hardened):
1. Cache check → 2. Safety gate → 3. Query analysis (intent, clarification, expansion)
4. Language detection → 5. Tri-modal retrieval (BM25 + Dense + Structured + Cross-Ref)
   with per-stream Top-K and dynamic weights
6. 4-stream fusion → 7. Context builder (clean structured input)
8. Mode routing (intent-based) → 9. Multi-Agent Debate OR Single-pass generation
   with debate timeout fallback
10. Hard grounding validation → 11. Post-response safety check
12. Execution layer (portals + procedures) → 13. Response structuring → SSE
"""
from __future__ import annotations
import asyncio
import json
import logging
import time
from typing import AsyncGenerator

import config
from models.schemas import (
    ChatRequest, StreamChunk, QueryAnalysis,
)
from services import retrieval, structured_nav, fusion, language, safety, grounding, cache, audit
from services import embeddings, query_engine, gemini_rest, execution
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


# ── Intent-based routing logic ──────────────────────────────────
def _route_mode(intent: str, requested_mode: str) -> str:
    """
    Route to debate or simple mode based on intent.
    - procedural / factual → always simple (debate is overkill)
    - situational / comparative / rights → respect user's requested mode
    """
    if intent in ("procedural", "factual"):
        return "simple"
    return requested_mode


def _get_intent_top_k(intent: str) -> dict[str, int]:
    """Get per-stream top-K limits adjusted by intent."""
    base = {
        "bm25": config.TOP_K_BM25,
        "dense": config.TOP_K_DENSE,
        "structured": config.TOP_K_STRUCTURED,
        "cross_ref": config.TOP_K_CROSS_REF,
    }
    if intent == "procedural":
        # Procedural needs fewer but more precise results
        base["bm25"] = min(base["bm25"], 5)
        base["dense"] = min(base["dense"], 4)
        base["cross_ref"] = min(base["cross_ref"], 2)
    elif intent == "factual":
        # Factual needs exact section matches
        base["structured"] = max(base["structured"], 6)
        base["bm25"] = min(base["bm25"], 6)
    elif intent in ("situational", "rights"):
        # These need broader semantic coverage
        base["dense"] = max(base["dense"], 8)
    return base


def _get_fusion_top_k(intent: str) -> int:
    """Get the final fusion top-K based on intent."""
    if intent in ("procedural", "factual"):
        return config.CONTEXT_MAX_SECTIONS
    return config.MAX_RETRIEVAL_RESULTS


# ── Pipeline Cache Helpers ──────────────────────────────────────
def _try_pipeline_cache(query: str, mode: str, lang: str) -> list[dict] | None:
    """Check pipeline cache for a matching response."""
    if not config.PIPELINE_CACHE_ENABLED:
        return None
    cache_key = cache.make_pipeline_key(query, mode, lang)
    return cache.get_pipeline(cache_key)


def _store_pipeline_cache(query: str, mode: str, lang: str, chunks: list[dict]):
    """Store pipeline response in cache."""
    if not config.PIPELINE_CACHE_ENABLED:
        return
    cache_key = cache.make_pipeline_key(query, mode, lang)
    cache.set_pipeline(cache_key, chunks)


# ── Fallback Response Builder ───────────────────────────────────
def _build_fallback(context: str, query: str) -> str:
    """Build a fallback response when LLM generation fails."""
    if context.strip():
        return (
            "Our AI synthesis engine is currently experiencing high load. "
            "However, our retrieval system has matched your query to the following legal provisions:\n\n"
            + context
        )
    return (
        "I apologize, but I was unable to process your query at this time. "
        "Please try again in a moment, or call NALSA Legal Aid at **15100** (toll-free) "
        "for free legal assistance."
    )


async def process_chat(
    request: ChatRequest,
    user_id: str | None = None,
) -> AsyncGenerator[StreamChunk, None]:
    """
    Process a chat request through the full hardened pipeline.
    Yields StreamChunk objects for SSE streaming.

    Pipeline stages:
    1. Session → 2. Rate Limit → 3. Safety → 4. Cache Check
    5. Language → 6. Query Analysis → 7. Retrieval (4-stream)
    8. Fusion + Context → 9. Mode Routing → 10. Generation (debate/simple)
    11. Hard Grounding → 12. Post-Response Safety → 13. Execution Layer
    14. Save + Metadata → done

    Any unhandled error → fallback response + done (never hang)
    """
    pipeline_start = time.monotonic()
    cacheable_chunks: list[dict] = []  # For pipeline cache

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

    # ── 3b. Urgency Detection ───────────────────────────────────────
    urgency = safety.detect_urgency(request.message)
    if urgency.level in ("critical", "high"):
        yield StreamChunk(type="urgency", data=urgency.model_dump())

    # ── 4. Pipeline Cache Check ─────────────────────────────────────
    detected_lang_early = request.language or language.detect_language(request.message)
    effective_mode = request.mode

    cached_response = _try_pipeline_cache(request.message, effective_mode, detected_lang_early)
    if cached_response is not None:
        logger.info("Pipeline cache HIT for query: %s", request.message[:60])
        yield StreamChunk(type="thinking", data={
            "message": "Retrieved from cache...",
            "cached": True,
        })
        for chunk_data in cached_response:
            yield StreamChunk(**chunk_data)
        yield StreamChunk(type="done", data={"session_id": session_id, "cached": True})
        # Still save messages for history
        response_text = ""
        for cd in cached_response:
            if cd.get("type") == "response":
                response_text += cd.get("data", {}).get("text", "")
        if response_text:
            await add_message(session_id, "user", request.message, {"cached": True})
            await add_message(session_id, "assistant", response_text, {"cached": True})
        return

    # ── MAIN PIPELINE (wrapped in try/except for failure flow) ─────
    try:
        await _run_main_pipeline(
            request, session_id, is_new_session, user_id,
            urgency, detected_lang_early, cacheable_chunks,
            pipeline_start,
        )
        async for chunk in _emit_pipeline_chunks(cacheable_chunks, session_id):
            yield chunk

    except Exception as e:
        # ── FAILURE FLOW: Always return a response ──────────────────
        logger.error("Pipeline error: %s", e, exc_info=True)
        fallback = _build_fallback("", request.message)
        yield StreamChunk(type="response", data={"text": fallback})
        yield StreamChunk(type="sources", data={
            "sources": [],
            "confidence": 0.1,
            "language": detected_lang_early,
            "mode": "fallback",
            "error": str(e),
        })
        yield StreamChunk(type="done", data={"session_id": session_id})


async def _emit_pipeline_chunks(
    cacheable_chunks: list[dict],
    session_id: str,
) -> AsyncGenerator[StreamChunk, None]:
    """Emit collected pipeline chunks and final done."""
    for chunk_data in cacheable_chunks:
        yield StreamChunk(**chunk_data)
    yield StreamChunk(type="done", data={"session_id": session_id})


async def _run_main_pipeline(
    request: ChatRequest,
    session_id: str,
    is_new_session: bool,
    user_id: str | None,
    urgency,
    detected_lang: str,
    cacheable_chunks: list[dict],
    pipeline_start: float,
):
    """
    Main pipeline logic. All chunks are collected into cacheable_chunks list.
    This is separated from process_chat to enable try/except failure flow.
    """

    # ── 5. Language Detection ───────────────────────────────────────
    cacheable_chunks.append({
        "type": "thinking",
        "data": {"message": "Analyzing your query...", "language": detected_lang},
    })

    # ── 6. Advanced Query Analysis ──────────────────────────────────
    query_analysis = await query_engine.analyze_query(request.message, detected_lang)

    cacheable_chunks.append({
        "type": "query_analysis",
        "data": {
            "intent": query_analysis.intent,
            "is_vague": query_analysis.is_vague,
            "was_clarified": query_analysis.was_clarified,
            "effective_query": query_analysis.effective_query,
            "parties": query_analysis.parties,
            "expanded_queries": len(query_analysis.retrieval_queries),
        },
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

    cacheable_chunks.append({
        "type": "thinking",
        "data": {"message": "Searching legal database (4 streams)..."},
    })

    # ── 8. Tri-Modal Retrieval (with per-stream Top-K) ──────────────
    top_k = _get_intent_top_k(query_analysis.intent)

    # Stream 1: BM25 (with query expansion)
    bm25_results = retrieval.multi_query_search(
        query_analysis.retrieval_queries or [retrieval_query],
        top_k=top_k["bm25"],
    )

    # Stream 2: Dense vector similarity
    dense_results = await embeddings.dense_search(retrieval_query, top_k=top_k["dense"])

    # Stream 3: Structured navigation
    struct_results = structured_nav.structured_search(retrieval_query, top_k=top_k["structured"])

    # Stream 4: Cross-reference graph traversal
    seed_sections = [s for s, _ in bm25_results[:3]] + [s for s, _ in struct_results[:2]]
    cross_ref_results = retrieval.cross_reference_search(seed_sections, depth=1)
    cross_ref_results = cross_ref_results[:top_k["cross_ref"]]

    # Corpus gap detection
    gap_analysis = retrieval.detect_corpus_gap(bm25_results, dense_results, struct_results)

    # ── 9. 4-Stream Fusion with Dynamic Weights ─────────────────────
    dynamic_weights = fusion.get_dynamic_weights(query_analysis.intent, retrieval_query)
    fusion_top_k = _get_fusion_top_k(query_analysis.intent)

    fused_results = fusion.fuse(
        bm25_results=bm25_results,
        structured_results=struct_results,
        top_k=fusion_top_k,
        dense_results=dense_results,
        cross_ref_results=cross_ref_results,
        weights=dynamic_weights,
    )
    sources = fusion.results_to_sources(fused_results)

    # ── 10. Context Builder (Clean Structured Input) ────────────────
    llm_context = fusion.build_llm_context(fused_results)
    display_context = fusion.build_context(fused_results)  # For fallback display

    cacheable_chunks.append({
        "type": "retrieval",
        "data": {
            "sources_found": len(fused_results),
            "sources": [s.model_dump() for s in sources[:5]],
            "streams": {
                "bm25": len(bm25_results),
                "dense": len(dense_results),
                "structured": len(struct_results),
                "cross_ref": len(cross_ref_results),
            },
            "gap_analysis": gap_analysis,
            "dynamic_weights": {k: round(v, 2) for k, v in dynamic_weights.items()},
        },
    })

    # ── 11. Mode Routing (Intent-Based) ─────────────────────────────
    routed_mode = _route_mode(query_analysis.intent, request.mode)
    use_debate = (
        config.DEBATE_ENABLED
        and routed_mode == "debate"
        and _client_ready
        and llm_context.strip()
    )

    # ── 12. Get Conversation History ────────────────────────────────
    history = await get_history(session_id, limit=10)

    # ── 13. Generate Response ───────────────────────────────────────
    lang_instruction = language.get_response_language_instruction(detected_lang)

    if use_debate:
        full_response, debate_confidence = await _run_debate_with_fallback(
            llm_context, display_context, request.message, session_id,
            lang_instruction, query_analysis.intent, history,
            detected_lang, cacheable_chunks,
        )
    else:
        full_response = await _run_simple_generation(
            llm_context, display_context, request.message, history,
            detected_lang, query_analysis, lang_instruction, cacheable_chunks,
        )
        debate_confidence = None

    if not full_response:
        return  # Error already handled in generation function

    # ── 14. Hard Grounding Validation ───────────────────────────────
    retrieved_sections = [sec for sec, _, _ in fused_results]
    grounding_report = grounding.validate_citations(full_response, retrieved_sections)

    # Apply hard grounding (strip ungrounded citations)
    full_response, grounding_report = grounding.hard_grounding_check(
        full_response, retrieved_sections, grounding_report,
    )

    # Compute confidence with enhanced multi-factor scoring
    retrieval_scores = [score for _, score, _ in fused_results]
    stream_agreement = gap_analysis.get("stream_agreement", 0)
    confidence = grounding.compute_confidence(
        retrieval_scores, grounding_report, bool(llm_context.strip()),
        debate_confidence=debate_confidence,
        stream_agreement=stream_agreement,
        gap_analysis=gap_analysis,
    )

    # ── 15. Post-Response Safety Check ──────────────────────────────
    if config.POST_RESPONSE_SAFETY:
        safety_check = safety.post_response_check(full_response)
        if not safety_check["safe"]:
            full_response = safety_check["sanitized_text"]
            logger.info("Post-response safety: %s", safety_check["warnings"])

    # ── 16. Low Confidence Flag ─────────────────────────────────────
    full_response = grounding.inject_uncertainty(full_response, confidence)

    # ── 17. Execution Layer ─────────────────────────────────────────
    full_response, exec_metadata = execution.enrich_response(
        full_response,
        intent=query_analysis.intent,
    )

    # ── 18. Add Disclaimer ──────────────────────────────────────────
    full_response = grounding.add_disclaimer(full_response)

    # ── 19. Emit final response (replace any previous response chunks) ──
    # Clear any existing response chunks (they were streamed during generation)
    # The final enriched response replaces them
    # We DON'T re-emit— the streaming already emitted tokens.
    # Instead we just use the full_response for saving purposes.

    # ── 20. Save Messages ──────────────────────────────────────────
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
        "execution": exec_metadata,
    })

    # Auto-title new sessions
    if is_new_session:
        asyncio.create_task(_auto_title_session(session_id, request.message))

    # Audit log
    pipeline_latency = (time.monotonic() - pipeline_start) * 1000
    await audit.log_query(session_id, request.message, detected_lang, urgency.level)

    # ── 21. Final metadata chunk ───────────────────────────────────
    cacheable_chunks.append({
        "type": "sources",
        "data": {
            "sources": [s.model_dump() for s in sources],
            "confidence": confidence,
            "grounding": grounding_report,
            "language": detected_lang,
            "urgency": urgency.model_dump(),
            "mode": "debate" if use_debate else "simple",
            "pipeline_latency_ms": round(pipeline_latency, 1),
            "gap_analysis": gap_analysis,
            "execution": exec_metadata,
        },
    })

    # Store in pipeline cache
    _store_pipeline_cache(request.message, request.mode, detected_lang, cacheable_chunks)


async def _run_debate_with_fallback(
    llm_context: str,
    display_context: str,
    query: str,
    session_id: str,
    lang_instruction: str,
    intent: str,
    history: list,
    detected_lang: str,
    cacheable_chunks: list[dict],
) -> tuple[str, float]:
    """
    Run debate with timeout fallback.
    If debate fails or times out, falls back to simple generation.

    Returns: (full_response_text, debate_confidence)
    """
    cacheable_chunks.append({
        "type": "thinking",
        "data": {"message": "Running multi-agent legal analysis..."},
    })

    try:
        full_response = ""
        debate_confidence = 0.5

        async def _run_debate():
            nonlocal full_response, debate_confidence
            async for chunk in debate_orchestrator.run_debate(
                context=llm_context,
                query=query,
                session_id=session_id,
                language_instruction=lang_instruction,
                intent=intent,
            ):
                if chunk.type == "response":
                    text = chunk.data.get("text", "")
                    full_response += text
                    cacheable_chunks.append(chunk.model_dump())
                elif chunk.type == "debate_complete":
                    debate_confidence = chunk.data.get("confidence", 0.5)
                    cacheable_chunks.append(chunk.model_dump())
                else:
                    cacheable_chunks.append(chunk.model_dump())

        # Run with timeout
        await asyncio.wait_for(
            _run_debate(),
            timeout=config.DEBATE_TIMEOUT_SECONDS,
        )

        return full_response, debate_confidence

    except asyncio.TimeoutError:
        logger.warning("Debate timed out after %ds — falling back to simple mode",
                       config.DEBATE_TIMEOUT_SECONDS)
        cacheable_chunks.append({
            "type": "thinking",
            "data": {"message": "Switching to instant mode (debate timed out)...", "fallback": True},
        })
        # Fall through to simple generation
    except Exception as e:
        logger.error("Debate failed: %s — falling back to simple mode", e)
        cacheable_chunks.append({
            "type": "thinking",
            "data": {"message": "Switching to instant mode...", "fallback": True},
        })

    # Fallback: simple generation
    query_analysis = await query_engine.analyze_query(query, detected_lang)
    fallback_response = await _run_simple_generation(
        llm_context, display_context, query, history,
        detected_lang, query_analysis, lang_instruction, cacheable_chunks,
    )
    return fallback_response or "", 0.4  # Lower confidence for fallback


async def _run_simple_generation(
    llm_context: str,
    display_context: str,
    query: str,
    history: list,
    detected_lang: str,
    query_analysis,
    lang_instruction: str,
    cacheable_chunks: list[dict],
) -> str | None:
    """
    Run single-pass LLM generation.
    Returns the full response text, or None if LLM is not available.
    """
    if not _client_ready:
        fallback_text = (
            "⚠️ LLM service is not configured. Please set GEMINI_API_KEY.\n\n"
            "Here are the relevant legal provisions:\n\n" + display_context
        )
        cacheable_chunks.append({"type": "response", "data": {"text": fallback_text}})
        return fallback_text

    system = SYSTEM_PROMPT.format(language_instruction=lang_instruction)
    messages = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        messages.append({"role": role, "parts": [{"text": msg["content"]}]})

    user_prompt = f"""## Retrieved Legal Context
{llm_context if llm_context else "No specific legal provisions were found for this query."}

## User's Question
{query}

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
            cacheable_chunks.append({"type": "response", "data": {"text": chunk_text}})

        return full_response

    except Exception as e:
        logger.error("LLM generation failed: %s", e)
        fallback_text = _build_fallback(display_context, query)
        cacheable_chunks.append({"type": "response", "data": {"text": fallback_text}})
        return fallback_text


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
