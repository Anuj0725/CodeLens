async def log_query(
    pool,
    query_text: str,
    retrieved_chunk_ids: list[str],
    reranked_chunk_ids: list[str],
    confidence_score: float,
    cache_hit: bool,
    latency_ms: dict,
) -> None:
    """
    Log a query to the query_logs table.
    
    Args:
        latency_ms: dict with keys like {"retrieval": 120, "rerank": 45, "generation": 800, "total": 965}
    """
    await pool.execute(
        """
        INSERT INTO query_logs (query_text, retrieved_chunk_ids, reranked_chunk_ids,
                                confidence_score, cache_hit, retrieval_latency_ms, rerank_latency_ms, generation_latency_ms, total_latency_ms)
        VALUES ($1, ($2::text[])::uuid[], ($3::text[])::uuid[], $4, $5, $6, $7, $8, $9)
        """,
        query_text,
        retrieved_chunk_ids,
        reranked_chunk_ids,
        confidence_score,
        cache_hit,
        latency_ms.get("retrieval"),
        latency_ms.get("rerank"),
        latency_ms.get("generation"),
        latency_ms.get("total")
    )
