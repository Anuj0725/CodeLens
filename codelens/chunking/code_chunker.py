import ast
import textwrap

from codelens.chunking.base import Chunk
from codelens.loaders.base import LoaderResult

_MAX_CLASS_LINES = 150


def chunk_python_code(loader_result: LoaderResult) -> list[Chunk]:
    """
    Parse a Python file with AST and split at function/class boundaries.

    Strategy:
    - Full file → parent chunk.
    - Top-level imports are collected as a prefix for context.
    - Each top-level function/async function → child chunk (with imports prepended).
    - Small classes (<150 lines) → single child chunk.
    - Large classes → one child per method, class body as parent-like context.
    - Falls back to returning just the parent if AST parsing fails.
    """
    source = loader_result.raw_text
    if not source.strip():
        return []

    parent = Chunk(
        chunk_text=source,
        chunk_type="parent",
        chunk_identifier="__root__",
        document_type=loader_result.document_type,
        language=loader_result.language,
        file_path=loader_result.file_path,
        repository=loader_result.repository,
        parent_chunk=None,
    )

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [parent]

    lines = source.splitlines(keepends=True)
    import_block = _extract_imports(tree, lines)

    chunks = [parent]

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn_text = _get_node_source(node, lines)
            child_text = f"{import_block}\n{fn_text}" if import_block else fn_text

            chunks.append(Chunk(
                chunk_text=child_text.strip(),
                chunk_type="child",
                chunk_identifier=node.name,
                document_type=loader_result.document_type,
                language=loader_result.language,
                file_path=loader_result.file_path,
                repository=loader_result.repository,
                parent_chunk=parent,
            ))

        elif isinstance(node, ast.ClassDef):
            class_source = _get_node_source(node, lines)
            class_lines = class_source.count("\n") + 1

            if class_lines <= _MAX_CLASS_LINES:
                child_text = f"{import_block}\n{class_source}" if import_block else class_source
                chunks.append(Chunk(
                    chunk_text=child_text.strip(),
                    chunk_type="child",
                    chunk_identifier=node.name,
                    document_type=loader_result.document_type,
                    language=loader_result.language,
                    file_path=loader_result.file_path,
                    repository=loader_result.repository,
                    parent_chunk=parent,
                ))
            else:
                # Large class: split into per-method chunks
                _chunk_large_class(
                    node, lines, import_block, loader_result, parent, chunks
                )

    return chunks


def _extract_imports(tree: ast.Module, lines: list[str]) -> str:
    """Collect all top-level import statements as a single string."""
    import_lines = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_lines.append(_get_node_source(node, lines).strip())
    return "\n".join(import_lines)


def _chunk_large_class(
    class_node: ast.ClassDef,
    lines: list[str],
    import_block: str,
    loader_result: LoaderResult,
    parent: Chunk,
    chunks: list[Chunk],
) -> None:
    """Split a large class into one child chunk per method."""
    class_name = class_node.name

    for node in ast.iter_child_nodes(class_node):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        method_source = _get_node_source(node, lines)
        # Dedent method source since it's indented inside the class
        method_source = textwrap.dedent(method_source)
        identifier = f"{class_name}.{node.name}"

        prefix = import_block
        class_header = f"class {class_name}:"
        context = f"{prefix}\n\n{class_header}\n" if prefix else f"{class_header}\n"

        child_text = f"{context}    # (method extracted from large class)\n\n{method_source}"

        chunks.append(Chunk(
            chunk_text=child_text.strip(),
            chunk_type="child",
            chunk_identifier=identifier,
            document_type=loader_result.document_type,
            language=loader_result.language,
            file_path=loader_result.file_path,
            repository=loader_result.repository,
            parent_chunk=parent,
        ))


def _get_node_source(node: ast.AST, lines: list[str]) -> str:
    """Extract the source code for an AST node using line numbers."""
    start = node.lineno - 1  # ast is 1-indexed
    end = node.end_lineno     # end_lineno is inclusive
    return "".join(lines[start:end])
