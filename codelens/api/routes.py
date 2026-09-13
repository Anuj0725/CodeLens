import logging
from fastapi import APIRouter, HTTPException

from codelens.api.schemas import (
    IngestRequest, IngestResponse,
    AskRequest, AskResponse,
    HealthResponse,
)
from codelens.loaders.github_loader import load_github
from codelens.loaders.web_loader import load_web_page
from codelens.indexing.indexer import ingest
from codelens.query_engine import ask

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok")


@router.post("/ingest", response_model=IngestResponse)
async def ingest_source(request: IngestRequest):
    """Ingest a GitHub repo or web page into CodeLens."""
    try:
        if request.source_type == "github":
            if not request.url.startswith("https://github.com/"):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid GitHub URL. Must start with 'https://github.com/'."
                )
            loader_results = load_github(request.url)
        elif request.source_type == "web":
            if not request.url.startswith(("http://", "https://")):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid URL. Must start with 'http://' or 'https://'."
                )
            loader_results = load_web_page(request.url)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported source_type: '{request.source_type}'. Use 'github' or 'web'."
            )

        if not loader_results:
            return IngestResponse(
                chunks_added=0, chunks_updated=0, chunks_skipped=0,
                message="No supported files found in the source."
            )

        stats = await ingest(loader_results)
        return IngestResponse(
            **stats,
            message=f"Successfully ingested {stats['chunks_added']} chunks from {request.source_type}."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """Ask a question about the indexed codebase."""
    try:
        result = await ask(request.query, repo_filter=request.repo_filter)
        return AskResponse(**result)
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
