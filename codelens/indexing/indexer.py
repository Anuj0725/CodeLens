import logging
from typing import List, Dict

from codelens.database import get_pool
from codelens.loaders.base import LoaderResult
from codelens.indexing.hasher import compute_hash
from codelens.indexing.embedder import Embedder
from codelens.chunking.code_chunker import chunk_python_code
from codelens.chunking.markdown_chunker import chunk_markdown
from codelens.chunking.fallback_chunker import chunk_fallback
from codelens.chunking.base import Chunk

logger = logging.getLogger(__name__)

# Module-level embedder instance
_embedder = None

def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder

async def ingest(loader_results: List[LoaderResult]) -> Dict[str, int]:
    """
    Full ingestion pipeline.
    Returns {"chunks_added": N, "chunks_updated": N, "chunks_skipped": N}
    """
    stats = {"chunks_added": 0, "chunks_updated": 0, "chunks_skipped": 0}
    
    if not loader_results:
        return stats
        
    pool = await get_pool()
    embedder = get_embedder()
    
    for result in loader_results:
        # Route to the appropriate chunker
        if result.language == "python":
            chunks = chunk_python_code(result)
        elif result.language == "markdown":
            chunks = chunk_markdown(result)
        else:
            chunks = chunk_fallback(result)
            
        if not chunks:
            continue
            
        # Compute hashes for all chunks
        for chunk in chunks:
            chunk.content_hash = compute_hash(chunk.chunk_text)
            
        # Group chunks by parent to ensure insertion order
        # A file might have 1 parent and multiple children
        parents = [c for c in chunks if c.chunk_type == "parent"]
        children = [c for c in chunks if c.chunk_type == "child"]
        
        # Batch embed children
        if children:
            child_texts = [c.chunk_text for c in children]
            embeddings = embedder.embed_texts(child_texts)
            for child, emb in zip(children, embeddings):
                child.embedding = emb
                
        # Insert parents first
        parent_id_map = {} # Maps chunk_identifier to db chunk_id
        
        for parent in parents:
            chunk_id, status = await _upsert_chunk(pool, parent, None, embedder.model_version)
            parent_id_map[parent.chunk_identifier] = chunk_id
            stats[status] += 1
            
        # Insert children
        for child in children:
            parent_db_id = parent_id_map.get(child.parent_chunk.chunk_identifier) if child.parent_chunk else None
            _, status = await _upsert_chunk(pool, child, parent_db_id, embedder.model_version)
            stats[status] += 1
            
    return stats


async def _upsert_chunk(pool, chunk: Chunk, parent_id: str, model_version: str) -> tuple[str, str]:
    """
    Upserts a single chunk into the database.
    Returns (chunk_id, status) where status is one of 'chunks_added', 'chunks_updated', 'chunks_skipped'.
    """
    # Check if chunk exists
    existing_row = await pool.fetchrow(
        """
        SELECT chunk_id, content_hash FROM chunks
        WHERE repository = $1 AND file_path = $2 AND chunk_identifier = $3 AND chunk_type = $4
        """,
        chunk.repository, chunk.file_path, chunk.chunk_identifier, chunk.chunk_type
    )
    
    embedding_attr = getattr(chunk, "embedding", None)
    embedding_str = str(embedding_attr) if embedding_attr is not None else None
    
    if existing_row:
        if existing_row["content_hash"] == chunk.content_hash:
            return existing_row["chunk_id"], "chunks_skipped"
        else:
            # Update existing chunk
            await pool.execute(
                """
                UPDATE chunks SET chunk_text = $1, content_hash = $2, embedding = $3,
                                  embedding_model_version = $4, updated_at = now()
                WHERE chunk_id = $5
                """,
                chunk.chunk_text, chunk.content_hash, embedding_str, model_version, existing_row["chunk_id"]
            )
            return existing_row["chunk_id"], "chunks_updated"
    else:
        # Insert new chunk
        chunk_id = await pool.fetchval(
            """
            INSERT INTO chunks (repository, file_path, chunk_identifier, language, document_type,
                                chunk_type, chunk_text, content_hash, embedding_model_version, embedding, parent_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING chunk_id
            """,
            chunk.repository, chunk.file_path, chunk.chunk_identifier, chunk.language, chunk.document_type,
            chunk.chunk_type, chunk.chunk_text, chunk.content_hash, model_version, embedding_str, parent_id
        )
        return chunk_id, "chunks_added"
