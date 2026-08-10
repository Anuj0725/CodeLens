from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration loaded from environment variables / .env file.

    Pydantic Settings reads these in priority order:
      1. Actual environment variables (highest)
      2. Values in the .env file
      3. Defaults defined here (lowest)

    Any missing required field (no default) causes a clear validation
    error at startup — not a silent None buried in runtime.
    """

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # don't error on unexpected env vars
    )

    # ── Database ──────────────────────────────────────────────
    database_url: str = "postgresql://codelens:codelens_dev@localhost:5432/codelens"

    # ── Redis ─────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── LLM ───────────────────────────────────────────────────
    llm_provider: str = "openai"  # "openai" or "anthropic"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # ── Embedding ─────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimensions: int = 384

    # ── Re-ranking ────────────────────────────────────────────
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # ── Retrieval tuning ──────────────────────────────────────
    rrf_k: int = 60                  # RRF smoothing constant
    top_n_retrieval: int = 20        # candidates from hybrid search
    top_k_rerank: int = 5            # kept after cross-encoder re-ranking
    confidence_threshold: float = 0.3

    # ── Cache ─────────────────────────────────────────────────
    cache_ttl_seconds: int = 3600

    # ── Ingestion ─────────────────────────────────────────────
    max_file_size_bytes: int = 512_000   # skip files larger than ~500KB
    chunk_size_tokens: int = 500         # target child chunk size
    chunk_overlap_tokens: int = 50       # overlap for fallback chunker


# Singleton — import this everywhere instead of creating new instances.
# Usage: from codelens.config import settings
settings = Settings()
