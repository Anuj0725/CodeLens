from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Chunk:
    """
    A single chunk of text ready for embedding and storage.
    Parent chunks hold full context; child chunks are retrieval targets.
    """
    chunk_text: str
    chunk_type: str            # "parent" or "child"
    chunk_identifier: str      # e.g. "## Installation" or "MyClass.my_method"
    document_type: str         # "code", "markdown", "docs_site", "blog"
    language: str
    file_path: str
    repository: str
    parent_chunk: Chunk | None = field(default=None, repr=False)
