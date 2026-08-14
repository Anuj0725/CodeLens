from pathlib import Path

from codelens.loaders.base import LoaderResult


def load_markdown(
    path: str,
    repository: str | None = None,
) -> list[LoaderResult]:
    """
    Read .md files from a file path or directory.

    If `path` is a single file, load that file.
    If `path` is a directory, recursively glob for **/*.md.
    """
    target = Path(path).resolve()

    if not target.exists():
        raise FileNotFoundError(f"Path does not exist: {target}")

    repo_name = repository or target.name

    if target.is_file():
        return [_read_single_file(target, repo_name)]

    md_files = sorted(target.rglob("*.md"))
    if not md_files:
        return []

    results = []
    for md_file in md_files:
        try:
            result = _read_single_file(md_file, repo_name)
            results.append(result)
        except (UnicodeDecodeError, PermissionError):
            # skip files that can't be read
            continue

    return results


def _read_single_file(file_path: Path, repository: str) -> LoaderResult:
    """Read a single markdown file and return a LoaderResult."""
    raw_text = file_path.read_text(encoding="utf-8")

    return LoaderResult(
        repository=repository,
        file_path=str(file_path),
        language="markdown",
        document_type="markdown",
        raw_text=raw_text,
    )
