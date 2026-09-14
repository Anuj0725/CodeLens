import pytest
from codelens.indexing.hasher import compute_hash
from codelens.indexing.embedder import Embedder


class TestHasher:
    def test_deterministic(self):
        assert compute_hash("def test(): pass") == compute_hash("def test(): pass")

    def test_different_inputs_different_hashes(self):
        assert compute_hash("hello") != compute_hash("world")

    def test_whitespace_sensitive(self):
        assert compute_hash("hello") != compute_hash("hello ")


@pytest.fixture(scope="session")
def embedder():
    return Embedder()

class TestEmbedder:
    def test_output_dimension(self, embedder):
        vec = embedder.embed_query("test query")
        assert len(vec) == 384

    def test_different_queries_different_vectors(self, embedder):
        v1 = embedder.embed_query("how does escape work")
        v2 = embedder.embed_query("what is the weather today")
        assert v1 != v2
