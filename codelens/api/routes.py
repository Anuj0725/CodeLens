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

@router.get("/repositories")
async def list_repositories():
    """Get a list of all uniquely indexed repositories."""
    try:
        from codelens.database import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT DISTINCT repository FROM chunks WHERE repository IS NOT NULL ORDER BY repository")
            repos = [row["repository"] for row in rows]
            return {"repositories": repos}
    except Exception as e:
        logger.error(f"Failed to list repositories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/repositories/{repo_path:path}")
async def delete_repository(repo_path: str):
    """Delete an indexed repository."""
    try:
        from codelens.database import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM chunks WHERE repository = $1", repo_path)
            deleted_count = int(result.split()[1]) if len(result.split()) > 1 else 0
            if deleted_count == 0:
                raise HTTPException(status_code=404, detail="Repository not found.")
            return {"message": f"Successfully deleted {repo_path}", "chunks_deleted": deleted_count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete repository {repo_path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
