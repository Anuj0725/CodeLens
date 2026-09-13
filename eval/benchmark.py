"""
Benchmark retrieval quality across 4 modes:
  1. Keyword-only (tsvector)
  2. Vector-only (pgvector cosine)
  3. Hybrid RRF (keyword + vector)
  4. Hybrid + Cross-Encoder Re-rank

Metrics: Precision@5, Recall@5, MRR (Mean Reciprocal Rank)
"""
import json
import asyncio
import sys
import os
import time

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codelens.database import get_pool, close_pool
from codelens.indexing.embedder import Embedder
from codelens.retrieval.hybrid_search import vector_search, keyword_search, hybrid_search
from codelens.retrieval.reranker import Reranker


def precision_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int = 5) -> float:
    """What fraction of top-k retrieved are relevant?"""
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for rid in top_k if rid in expected_ids)
    return hits / len(top_k)


def recall_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int = 5) -> float:
    """What fraction of expected were found in top-k?"""
    if not expected_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for eid in expected_ids if eid in top_k)
    return hits / len(expected_ids)


def mrr(retrieved_ids: list[str], expected_ids: list[str]) -> float:
    """Reciprocal rank of the first relevant result."""
    for i, rid in enumerate(retrieved_ids):
        if rid in expected_ids:
            return 1.0 / (i + 1)
    return 0.0


async def run_benchmark():
    # Load questions
    with open("eval/test_questions.json") as f:
        questions = json.load(f)

    pool = await get_pool()
    embedder = Embedder()
    reranker = Reranker()

    # Results: mode -> category -> list of metric dicts
    modes = ["Keyword", "Vector", "Hybrid", "Hybrid+Rerank"]
    results = {mode: [] for mode in modes}

    print(f"Running benchmark on {len(questions)} questions...\n")

    for i, q in enumerate(questions):
        query = q["query"]
        expected = set(q["expected_chunk_ids"])
        category = q["category"]

        # Embed query once
        query_vec = embedder.embed_query(query)

        # 1. Keyword-only
        kw_results = await keyword_search(query, pool, limit=20)
        kw_ids = [str(r["chunk_id"]) for r in kw_results]

        # 2. Vector-only
        vec_results = await vector_search(query_vec, pool, limit=20)
        vec_ids = [str(r["chunk_id"]) for r in vec_results]

        # 3. Hybrid RRF
        hyb_results = await hybrid_search(query, query_vec, pool, limit=20)
        hyb_ids = [str(r["chunk_id"]) for r in hyb_results]

        # 4. Hybrid + Rerank
        reranked = reranker.rerank(query, hyb_results, top_k=10)
        rerank_ids = [str(r["chunk_id"]) for r in reranked]

        # Compute metrics for each mode
        for mode, ids in [
            ("Keyword", kw_ids),
            ("Vector", vec_ids),
            ("Hybrid", hyb_ids),
            ("Hybrid+Rerank", rerank_ids),
        ]:
            results[mode].append({
                "category": category,
                "precision": precision_at_k(ids, expected),
                "recall": recall_at_k(ids, expected),
                "mrr": mrr(ids, expected),
            })

        print(f"  [{i+1}/{len(questions)}] {query[:60]}...")

    # ── Print results table ──────────────────────────────────
    categories = ["code_specific", "conceptual", "exact_match", "Overall"]

    print("\n" + "=" * 80)
    print(f"{'':20s} | {'Keyword':>10s} | {'Vector':>10s} | {'Hybrid':>10s} | {'Hyb+Rerank':>10s}")
    print("-" * 80)

    for metric_name, metric_key in [("Precision@5", "precision"), ("Recall@5", "recall"), ("MRR", "mrr")]:
        print(f"\n  {metric_name}")
        print(f"  {'-' * 74}")
        for cat in categories:
            row = []
            for mode in modes:
                if cat == "Overall":
                    vals = [r[metric_key] for r in results[mode]]
                else:
                    vals = [r[metric_key] for r in results[mode] if r["category"] == cat]
                avg = sum(vals) / len(vals) if vals else 0.0
                row.append(f"{avg:.3f}")
            print(f"  {cat:20s} | {row[0]:>10s} | {row[1]:>10s} | {row[2]:>10s} | {row[3]:>10s}")

    print("\n" + "=" * 80)

    await close_pool()


if __name__ == "__main__":
    asyncio.run(run_benchmark())
