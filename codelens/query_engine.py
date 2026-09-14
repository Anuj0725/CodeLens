import time
import asyncio
import logging
from codelens.config import settings
from codelens.indexing.embedder import Embedder
from codelens.retrieval.hybrid_search import hybrid_search
from codelens.retrieval.reranker import Reranker
from codelens.retrieval.confidence import check_confidence
from codelens.generation.context_builder import reconstruct_context, build_prompt
from codelens.generation.llm_client import LLMClient
from codelens.cache.redis_cache import ResponseCache
from codelens.cache.query_logger import log_query
from codelens.database import get_pool

logger = logging.getLogger(__name__)

# Module-level singletons — initialized lazily
_embedder: Embedder | None = None
_reranker: Reranker | None = None
_llm: LLMClient | None = None
_cache: ResponseCache | None = None


def _get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


def _get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker


def _get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


def _get_cache() -> ResponseCache:
    global _cache
    if _cache is None:
        _cache = ResponseCache()
    return _cache


async def ask(query: str, repo_filter: str | None = None) -> dict:
    """
    Full RAG pipeline: query -> answer with citations.
    
    Returns:
        {
            "answer": str,
            "confidence_score": float,
            "sources": [{"file_path": str, "repository": str, "chunk_identifier": str}, ...],
            "cache_hit": bool,
            "latency_ms": {"retrieval": int, "rerank": int, "generation": int, "total": int}
        }
    """
    total_start = time.perf_counter()
    latency_ms = {}
    cache = _get_cache()

    # ── 1. Cache check ──────────────────────────────────────
    cached = await cache.get(query)
    if cached:
        # Still log the cache hit
        pool = await get_pool()
        await log_query(
            pool, query,
            retrieved_chunk_ids=[],
            reranked_chunk_ids=[],
            confidence_score=cached.get("confidence_score", 0.0),
            cache_hit=True,
            latency_ms={"total": int((time.perf_counter() - total_start) * 1000)},
        )
        cached["cache_hit"] = True
        return cached

    embedder = _get_embedder()
    reranker = _get_reranker()
    llm = _get_llm()
    pool = await get_pool()

    
    # 🔍 1.5 Optional Autocorrect via LLM
    try:
        t0 = time.perf_counter()
        autocorrect_prompt = f"Fix any spelling mistakes or typos in this search query. Return ONLY the corrected query string, nothing else. Do not answer it. Query: {query}"
        system_prompt = "You are an autocorrect API. You return exactly the corrected string without quotes or markdown."
        corrected_query = await llm.generate(autocorrect_prompt, system_prompt)
        corrected_query = corrected_query.strip(' \n\r\t"\'')
        
        # If it returned a massive hallucination, fallback to original
        if len(corrected_query) < len(query) + 20 and len(corrected_query) > 0:
            query = corrected_query
            
        latency_ms["autocorrect"] = int((time.perf_counter() - t0) * 1000)
    except Exception as e:
        logger.warning(f"Autocorrect failed, continuing with original query: {e}")

    # ── 2. Embed query ──────────────────────────────────────
    query_vec = embedder.embed_query(query)

    # ── 3. Hybrid retrieval (RRF) ───────────────────────────
    t0 = time.perf_counter()
    hybrid_results = await hybrid_search(
        query, query_vec, pool,
        repo_filter=repo_filter,
        limit=settings.top_n_retrieval,
    )
    latency_ms["retrieval"] = int((time.perf_counter() - t0) * 1000)

    if not hybrid_results:
        return await _no_results_response(query, latency_ms, total_start, pool)

    # ── 4. Cross-encoder rerank ─────────────────────────────
    t0 = time.perf_counter()
    reranked = reranker.rerank(query, hybrid_results, top_k=settings.top_k_rerank)
    latency_ms["rerank"] = int((time.perf_counter() - t0) * 1000)

    # ── 5. Confidence gate ──────────────────────────────────
    top_score = reranked[0]["rerank_score"]
    confident = check_confidence(top_score)

    if not confident:
        return await _no_results_response(query, latency_ms, total_start, pool, top_score)

    # ── 6. Parent context reconstruction ────────────────────
    context_groups = await reconstruct_context(reranked, pool)

    # ── 7. Build prompt ─────────────────────────────────────
    user_prompt, system_prompt = build_prompt(query, context_groups)

    # ── 8. LLM generation ───────────────────────────────────
    t0 = time.perf_counter()
    try:
        answer = await asyncio.wait_for(
            llm.generate(user_prompt, system_prompt),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        logger.error("LLM generation timed out after 30s")
        answer = "The AI model took too long to respond. The relevant source code was found (see sources below), but the answer could not be generated in time."
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        answer = f"Answer generation failed: {str(e)}. The relevant source code was found (see sources below)."
    latency_ms["generation"] = int((time.perf_counter() - t0) * 1000)

    # ── 9. Assemble response ────────────────────────────────
    sources = [
        {
            "file_path": r["file_path"],
            "repository": r["repository"],
            "chunk_identifier": r.get("chunk_identifier", ""),
        }
        for r in reranked
    ]

    latency_ms["total"] = int((time.perf_counter() - total_start) * 1000)

    response = {
        "answer": answer,
        "confidence_score": float(top_score),
        "sources": sources,
        "cache_hit": False,
        "latency_ms": latency_ms,
    }

    # ── 10. Cache write ─────────────────────────────────────
    await cache.set(query, response)

    # ── 11. Query logging ───────────────────────────────────
    await log_query(
        pool, query,
        retrieved_chunk_ids=[str(r["chunk_id"]) for r in hybrid_results[:5]],
        reranked_chunk_ids=[str(r["chunk_id"]) for r in reranked],
        confidence_score=float(top_score),
        cache_hit=False,
        latency_ms=latency_ms,
    )

    return response


async def _no_results_response(query, latency_ms, total_start, pool, score=None):
    """Build a 'no results' response and log it."""
    latency_ms["total"] = int((time.perf_counter() - total_start) * 1000)
    response = {
        "answer": "I couldn't find relevant information in the indexed codebase to answer this question.",
        "confidence_score": float(score) if score is not None else 0.0,
        "sources": [],
        "cache_hit": False,
        "latency_ms": latency_ms,
    }
    await log_query(
        pool, query,
        retrieved_chunk_ids=[],
        reranked_chunk_ids=[],
        confidence_score=response["confidence_score"],
        cache_hit=False,
        latency_ms=latency_ms,
    )
    return response
