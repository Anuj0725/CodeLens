from sentence_transformers import SentenceTransformer

from codelens.config import settings


class Embedder:
    """
    Wraps a SentenceTransformer model for generating text embeddings.
    Loaded once at init, reused across all embed calls.
    """

    def __init__(self, model_name: str | None = None):
        self._model_name = model_name or settings.embedding_model
        self._model = SentenceTransformer(self._model_name)

    @property
    def model_version(self) -> str:
        return self._model_name

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Encode a batch of texts into dense vectors.
        Returns a list of float lists, each of length 384.
        """
        embeddings = self._model.encode(
            texts,
            show_progress_bar=False,
            normalize_embeddings=True,
            batch_size=64,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        return self.embed_texts([query])[0]
