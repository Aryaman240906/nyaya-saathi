"""Application configuration loaded from environment variables."""
import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# ── Core ────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
CORPUS_DIR: Path = BASE_DIR / os.getenv("CORPUS_DIR", "./data/corpus")
PROCEDURES_DIR: Path = BASE_DIR / os.getenv("PROCEDURES_DIR", "./data/procedures")
DATABASE_PATH: Path = BASE_DIR / os.getenv("DATABASE_PATH", "./data/nyaya_saathi.db")
EMBEDDINGS_DIR: Path = BASE_DIR / os.getenv("EMBEDDINGS_DIR", "./data/embeddings")

MAX_RETRIEVAL_RESULTS: int = int(os.getenv("MAX_RETRIEVAL_RESULTS", "10"))
CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.3"))
FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

# ── LLM Models ──────────────────────────────────────────────────────
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_EMBEDDING_MODEL: str = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

# ── Authentication ──────────────────────────────────────────────────
def _get_stable_jwt_secret() -> str:
    """Get or create a stable JWT secret that persists across restarts."""
    secret_file = BASE_DIR / ".jwt_secret"
    env_secret = os.getenv("JWT_SECRET", "")
    if env_secret:
        return env_secret
    if secret_file.exists():
        return secret_file.read_text().strip()
    new_secret = secrets.token_urlsafe(48)
    secret_file.write_text(new_secret)
    return new_secret

JWT_SECRET: str = _get_stable_jwt_secret()
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
ALLOW_ANONYMOUS: bool = os.getenv("ALLOW_ANONYMOUS", "true").lower() == "true"

# ── Cache ───────────────────────────────────────────────────────────
CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "3600"))       # 1 hour
CACHE_MAX_ENTRIES: int = int(os.getenv("CACHE_MAX_ENTRIES", "1000"))
CACHE_LLM_TTL: int = int(os.getenv("CACHE_LLM_TTL", "1800"))              # 30 min

# ── Debate Engine ───────────────────────────────────────────────────
DEBATE_ENABLED: bool = os.getenv("DEBATE_ENABLED", "true").lower() == "true"
DEBATE_MAX_TOKENS_PER_AGENT: int = int(os.getenv("DEBATE_MAX_TOKENS_PER_AGENT", "2048"))
DEBATE_TEMPERATURE: float = float(os.getenv("DEBATE_TEMPERATURE", "0.2"))
DEBATE_FALLBACK_TO_SIMPLE: bool = True  # If debate fails, fall back to single-pass

# ── Query Engine ────────────────────────────────────────────────────
QUERY_EXPANSION_ENABLED: bool = os.getenv("QUERY_EXPANSION_ENABLED", "true").lower() == "true"
SEMANTIC_CLARIFIER_ENABLED: bool = os.getenv("SEMANTIC_CLARIFIER_ENABLED", "true").lower() == "true"
MAX_EXPANDED_QUERIES: int = int(os.getenv("MAX_EXPANDED_QUERIES", "3"))

# ── Retrieval Weights (for weighted RRF) ────────────────────────────
WEIGHT_BM25: float = float(os.getenv("WEIGHT_BM25", "1.0"))
WEIGHT_DENSE: float = float(os.getenv("WEIGHT_DENSE", "0.8"))
WEIGHT_STRUCTURED: float = float(os.getenv("WEIGHT_STRUCTURED", "0.9"))
WEIGHT_CROSS_REF: float = float(os.getenv("WEIGHT_CROSS_REF", "0.6"))

# ── Audit ───────────────────────────────────────────────────────────
AUDIT_ENABLED: bool = os.getenv("AUDIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
