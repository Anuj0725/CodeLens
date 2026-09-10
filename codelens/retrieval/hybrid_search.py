from typing import List, Dict, Any, Optional

from codelens.config import settings

async def vector_search(
    query_embedding: List[float],
    pool,
    repo_filter: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Cosine similarity search using pgvector.
    Returns child chunks ordered by similarity (closest first).
    """
    query = """
        SELECT chunk_id, file_path, chunk_identifier, chunk_text, repository,
               language, document_type, parent_id,
               1 - (embedding <=> $1::vector) AS similarity_score
        FROM chunks
        WHERE chunk_type = 'child'
          AND ($2::text IS NULL OR repository = $2)
        ORDER BY embedding <=> $1::vector
        LIMIT $3
    """
    
    # Format the list of floats into a string like "[0.1, 0.2, ...]"
    embedding_str = str(query_embedding)
    
    # asyncpg's fetch returns Record objects, convert them to dicts
    records = await pool.fetch(query, embedding_str, repo_filter, limit)
    
    return [dict(record) for record in records]

async def keyword_search(
    query_text: str,
    pool,
    repo_filter: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """
    Full-text keyword search using PostgreSQL tsvector.
    Returns child chunks ordered by text relevance.
    """
    query = """
        SELECT chunk_id, file_path, chunk_identifier, chunk_text, repository,
               language, document_type, parent_id,
               ts_rank_cd(tsvector_content, websearch_to_tsquery('english', $1)) AS keyword_score
        FROM chunks
        WHERE chunk_type = 'child'
          AND tsvector_content @@ websearch_to_tsquery('english', $1)
          AND ($2::text IS NULL OR repository = $2)
        ORDER BY keyword_score DESC
        LIMIT $3
    """
    records = await pool.fetch(query, query_text, repo_filter, limit)
    return [dict(record) for record in records]

async def hybrid_search(
    query_text: str,
    query_embedding: list[float],
    pool,
    repo_filter: str | None = None,
    limit: int = 20,
    rrf_k: int | None = None,
) -> list[dict]:
    """
    Hybrid search combining vector similarity and keyword matching
    using Reciprocal Rank Fusion (RRF).
    """
    if rrf_k is None:
        rrf_k = settings.rrf_k

    query = """
        WITH vector_results AS (
            SELECT chunk_id, file_path, chunk_identifier, chunk_text, repository,
                   language, document_type, parent_id,
                   ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) AS vector_rank
            FROM chunks
            WHERE chunk_type = 'child'
              AND ($3::text IS NULL OR repository = $3)
            ORDER BY embedding <=> $1::vector
            LIMIT $4
        ),
        keyword_results AS (
            SELECT chunk_id, file_path, chunk_identifier, chunk_text, repository,
                   language, document_type, parent_id,
                   ROW_NUMBER() OVER (ORDER BY ts_rank_cd(tsvector_content, websearch_to_tsquery('english', $2)) DESC) AS keyword_rank
            FROM chunks
            WHERE chunk_type = 'child'
              AND tsvector_content @@ websearch_to_tsquery('english', $2)
              AND ($3::text IS NULL OR repository = $3)
            ORDER BY ts_rank_cd(tsvector_content, websearch_to_tsquery('english', $2)) DESC
            LIMIT $4
        )
        SELECT
            COALESCE(v.chunk_id, k.chunk_id) AS chunk_id,
            COALESCE(v.file_path, k.file_path) AS file_path,
            COALESCE(v.chunk_identifier, k.chunk_identifier) AS chunk_identifier,
            COALESCE(v.chunk_text, k.chunk_text) AS chunk_text,
            COALESCE(v.repository, k.repository) AS repository,
            COALESCE(v.language, k.language) AS language,
            COALESCE(v.document_type, k.document_type) AS document_type,
            COALESCE(v.parent_id, k.parent_id) AS parent_id,
            COALESCE(1.0 / ($5 + v.vector_rank), 0.0) +
            COALESCE(1.0 / ($5 + k.keyword_rank), 0.0) AS rrf_score
        FROM vector_results v
        FULL OUTER JOIN keyword_results k ON v.chunk_id = k.chunk_id
        ORDER BY rrf_score DESC
        LIMIT $4
    """
    
    embedding_str = str(query_embedding)
    records = await pool.fetch(query, embedding_str, query_text, repo_filter, limit, rrf_k)
    return [dict(record) for record in records]
