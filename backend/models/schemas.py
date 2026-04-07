"""Pydantic schemas for request/response validation."""
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr
import uuid


# ── Auth Models ─────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    name: str = Field(..., min_length=1, max_length=100)

class UserLogin(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)

class UserProfile(BaseModel):
    id: str
    email: str
    name: str
    preferred_language: str = "en"
    created_at: str = ""

class UserUpdate(BaseModel):
    name: Optional[str] = None
    preferred_language: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile

class RefreshRequest(BaseModel):
    refresh_token: str


# ── Request Models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None
    language: Optional[str] = None
    mode: str = "debate"  # "debate" | "simple" — toggles multi-agent vs single-pass


class DocumentAnalysisRequest(BaseModel):
    text: str = Field(..., min_length=10)
    language: Optional[str] = None


# ── Response Models ─────────────────────────────────────────────────

class LawCitation(BaseModel):
    act: str
    section: str
    title: str
    text: str
    simplified: str = ""


class ProcedureStep(BaseModel):
    step_number: int
    action: str
    details: str
    timeline: Optional[str] = None
    documents_needed: List[str] = []


class Authority(BaseModel):
    name: str
    type: str
    contact: str = ""
    url: str = ""


class Source(BaseModel):
    act: str
    section: str
    title: str
    relevance_score: float
    retrieval_method: str = "bm25"


class UrgencyInfo(BaseModel):
    level: str = "low"
    message: str = ""
    helplines: List[dict] = []
    immediate_actions: List[str] = []


class LegalResponse(BaseModel):
    session_id: str
    applicable_law: List[LawCitation] = []
    simplified_explanation: str = ""
    your_rights: List[str] = []
    next_steps: List[ProcedureStep] = []
    required_documents: List[str] = []
    relevant_authorities: List[Authority] = []
    urgency: UrgencyInfo = UrgencyInfo()
    sources: List[Source] = []
    confidence_score: float = 0.0
    language: str = "en"
    disclaimer: str = ("This information is for educational purposes only and does not "
                       "constitute legal advice. Please consult a qualified lawyer for "
                       "specific legal matters.")


class StreamChunk(BaseModel):
    """Individual chunk in SSE stream — expanded for debate engine."""
    type: str  # See StreamType below
    data: dict = {}


# Stream chunk types:
# "thinking"           - Processing status updates
# "retrieval"          - Retrieval results summary
# "urgency"            - Urgency detection alert
# "response"           - Final response text (streamed)
# "sources"            - Source citations + metadata
# "done"               - Stream complete
# "error"              - Error occurred
# "query_analysis"     - Query engine analysis results
# "debate_start"       - Debate pipeline starting
# "debate_prosecutor"  - Prosecutor agent status/result
# "debate_defense"     - Defense agent status/result
# "debate_validator"   - Validator agent status/result
# "debate_procedure"   - Procedure agent status/result
# "debate_complete"    - Full debate metadata
# "pipeline_state"     - Pipeline node state update


# ── Query Analysis Model ────────────────────────────────────────────

class QueryAnalysis(BaseModel):
    """Result of advanced query analysis."""
    original_query: str
    effective_query: str
    retrieval_queries: List[str] = []
    intent: str = "situational"
    parties: List[str] = []
    is_vague: bool = False
    was_clarified: bool = False
    language: str = "en"


# ── Debate Models ───────────────────────────────────────────────────

class ReasonNode(BaseModel):
    """A node in the reason graph visualization."""
    id: str
    type: str  # "section" | "right" | "action" | "authority"
    label: str
    detail: str = ""
    act: str = ""
    section: str = ""
    confidence: float = 1.0


class ReasonEdge(BaseModel):
    """An edge in the reason graph."""
    source: str
    target: str
    label: str = ""
    weight: float = 1.0


class ReasonGraph(BaseModel):
    """Directed graph of legal reasoning."""
    nodes: List[ReasonNode] = []
    edges: List[ReasonEdge] = []


class PipelineNodeState(BaseModel):
    """State of a single pipeline node for canvas visualization."""
    id: str
    name: str
    status: str = "idle"  # "idle" | "running" | "done" | "error"
    latency_ms: float = 0
    detail: str = ""


class PipelineState(BaseModel):
    """Full pipeline state for canvas visualization."""
    session_id: str = ""
    nodes: List[PipelineNodeState] = []
    current_stage: str = ""


# ── Procedure Models ────────────────────────────────────────────────

class ProcedureWorkflow(BaseModel):
    id: str
    title: str
    title_hi: str = ""
    description: str
    category: str
    steps: List[ProcedureStep] = []
    required_documents: List[str] = []
    relevant_authorities: List[Authority] = []
    estimated_timeline: str = ""
    helplines: List[dict] = []
    tips: List[str] = []


# ── Rights Models ───────────────────────────────────────────────────

class RightInfo(BaseModel):
    right: str
    article_or_section: str
    act: str
    explanation: str
    how_to_exercise: str = ""


class RightsCategory(BaseModel):
    category: str
    rights: List[RightInfo] = []


# ── Corpus Models ───────────────────────────────────────────────────

class LegalSection(BaseModel):
    id: str
    act: str
    short_name: str
    section_number: str
    title: str
    chapter: str = ""
    text: str
    simplified: str = ""
    related_sections: List[str] = []
    keywords: List[str] = []
    category: str = ""
    subcategory: str = ""
    punishment: str = ""


# ── Session/History Models ──────────────────────────────────────────

class SessionListItem(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    language: str = "en"
    last_message_preview: str = ""
    message_count: int = 0

class ChatHistoryItem(BaseModel):
    role: str
    content: str
    metadata: dict = {}
    created_at: str = ""

class BookmarkItem(BaseModel):
    section_id: str
    act: str = ""
    section_number: str = ""
    title: str = ""
    note: str = ""

class BookmarkResponse(BaseModel):
    id: str
    section_id: str
    act: str = ""
    section_number: str = ""
    title: str = ""
    note: str = ""
    created_at: str = ""
