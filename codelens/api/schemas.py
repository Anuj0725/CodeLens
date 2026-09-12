from pydantic import BaseModel, HttpUrl


class IngestRequest(BaseModel):
    """Request to ingest a source into CodeLens."""
    source_type: str  # "github", "web", "markdown"
    url: str
    # For markdown: raw text can be passed instead of URL
    raw_text: str | None = None


class IngestResponse(BaseModel):
    """Response after ingestion."""
    chunks_added: int
    chunks_updated: int
    chunks_skipped: int
    message: str


class AskRequest(BaseModel):
    """Request to ask a question."""
    query: str
    repo_filter: str | None = None


class AskResponse(BaseModel):
    """Response with grounded answer."""
    answer: str
    confidence_score: float
    sources: list[dict]
    cache_hit: bool
    latency_ms: dict


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
