from typing import List, Dict, Any, Optional

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
