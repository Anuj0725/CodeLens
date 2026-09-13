from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Request to ingest a source into CodeLens."""
    source_type: str = Field(..., pattern="^(github|web)$", description="Source type: 'github' or 'web'")
    url: str = Field(..., min_length=10, description="URL to ingest")
    raw_text: str | None = None


class IngestResponse(BaseModel):
    """Response after ingestion."""
    chunks_added: int
    chunks_updated: int
    chunks_skipped: int
    message: str


class AskRequest(BaseModel):
    """Request to ask a question."""
    query: str = Field(..., min_length=3, max_length=1000, description="Your question")
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
