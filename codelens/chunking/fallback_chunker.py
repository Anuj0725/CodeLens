from codelens.chunking.base import Chunk
from codelens.config import settings
from codelens.loaders.base import LoaderResult


def chunk_fallback(
    loader_result: LoaderResult,
    max_tokens: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """
    Simple token-count-based splitter for files that don't have a
    specialized chunker (e.g. .js, .java, .go, .rst, .txt).

    Splits text into overlapping windows of approximately `max_tokens` words.
    Full text becomes the parent; each window becomes a child.
    """
    max_tokens = max_tokens or settings.chunk_size_tokens
    overlap = overlap or settings.chunk_overlap_tokens

    text = loader_result.raw_text
    if not text.strip():
        return []

    parent = Chunk(
        chunk_text=text,
        chunk_type="parent",
        chunk_identifier="__root__",
        document_type=loader_result.document_type,
        language=loader_result.language,
        file_path=loader_result.file_path,
        repository=loader_result.repository,
        parent_chunk=None,
    )

    words = text.split()

    # If the whole file fits in one chunk, just return the parent
    if len(words) <= max_tokens:
        return [parent]

    chunks = [parent]
    start = 0
    part_num = 0

    while start < len(words):
        end = min(start + max_tokens, len(words))
        window_text = " ".join(words[start:end])
        part_num += 1

        chunks.append(Chunk(
            chunk_text=window_text,
            chunk_type="child",
            chunk_identifier=f"__part_{part_num}__",
            document_type=loader_result.document_type,
            language=loader_result.language,
            file_path=loader_result.file_path,
            repository=loader_result.repository,
            parent_chunk=parent,
        ))

        if end >= len(words):
            break
        start = end - overlap

    return chunks
