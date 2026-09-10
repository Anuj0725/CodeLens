from sentence_transformers import CrossEncoder
from codelens.config import settings

class Reranker:
    """
    Cross-encoder re-ranker for improving retrieval precision.
    Scores each (query, chunk_text) pair directly — more accurate
    than bi-encoder similarity but slower (that's why we only re-rank top-N).
    """

    def __init__(self, model_name: str | None = None):
        self._model_name = model_name or settings.reranker_model
        self._model = CrossEncoder(self._model_name)

    @property
    def model_version(self) -> str:
        return self._model_name

    def rerank(self, query: str, chunks: list[dict], top_k: int | None = None) -> list[dict]:
        """
        Re-score and re-order chunks based on cross-encoder relevance.
        
        Args:
            query: The user's search query
            chunks: List of chunk dicts from hybrid search (must have 'chunk_text' key)
            top_k: Number of top results to return (default: settings.top_k_rerank)
            
        Returns:
            Top-k chunks sorted by cross-encoder score, each with 'rerank_score' added.
        """
        if not chunks:
            return []
            
        if top_k is None:
            top_k = settings.top_k_rerank
            
        # Create pairs of (query, document)
        pairs = [[query, chunk["chunk_text"]] for chunk in chunks]
        
        # Predict scores
        scores = self._model.predict(pairs)
        
        # Attach scores to chunks and convert numpy floats to native python floats
        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = float(score)
            
        # Sort chunks by score descending
        chunks.sort(key=lambda x: x["rerank_score"], reverse=True)
        
        # Return top_k
        return chunks[:top_k]
