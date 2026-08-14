import re

from codelens.chunking.base import Chunk
from codelens.loaders.base import LoaderResult

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def chunk_markdown(loader_result: LoaderResult) -> list[Chunk]:
    """
    Split a markdown document by headings into parent + child chunks.

    Strategy:
    - The full document becomes the parent chunk (identifier = "__root__").
    - Each heading section becomes a child chunk.
    - Sections too small (<30 chars of content) are merged into the
      previous section to avoid noise chunks.
    """
    text = loader_result.raw_text
    if not text.strip():
        return []

    # Build the parent chunk (full document)
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

    # Find all heading positions
    sections = _split_by_headings(text)

    if len(sections) <= 1:
        # No headings or single section — parent is enough
        return [parent]

    chunks = [parent]

    for identifier, section_text in sections:
        stripped = section_text.strip()
        if len(stripped) < 30:
            continue

        chunks.append(Chunk(
            chunk_text=stripped,
            chunk_type="child",
            chunk_identifier=identifier,
            document_type=loader_result.document_type,
            language=loader_result.language,
            file_path=loader_result.file_path,
            repository=loader_result.repository,
            parent_chunk=parent,
        ))

    return chunks


def _split_by_headings(text: str) -> list[tuple[str, str]]:
    """
    Split markdown text into (heading_identifier, section_text) pairs.

    Content before the first heading gets identifier "__preamble__".
    """
    matches = list(_HEADING_RE.finditer(text))

    if not matches:
        return [("__preamble__", text)]

    sections = []

    # Content before first heading
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()]
        if preamble.strip():
            sections.append(("__preamble__", preamble))

    for i, match in enumerate(matches):
        hashes = match.group(1)
        title = match.group(2).strip()
        identifier = f"{hashes} {title}"

        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_text = text[start:end]

        sections.append((identifier, section_text))

    return sections
