import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from codelens.database import get_pool, close_pool
from codelens.api.routes import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup, clean up on shutdown."""
    logger.info("Starting CodeLens API...")
    
    # Initialize DB pool on startup
    pool = await get_pool()
    logger.info(f"Database pool ready ({pool.get_size()} connections)")

    yield

    # Cleanup on shutdown
    logger.info("Shutting down CodeLens API...")
    await close_pool()
    logger.info("Database pool closed.")


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="CodeLens",
    description="AI-powered code search and Q&A over your repositories.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
