import shutil
import subprocess
import tempfile
from pathlib import Path

from codelens.config import settings
from codelens.loaders.base import LoaderResult

# Directories to skip during tree walk
_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", "venv", ".venv",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".eggs", ".idea", ".vscode", "vendor", "target",
}

# Extension → (language, document_type)
_EXTENSION_MAP: dict[str, tuple[str, str]] = {
    ".py":   ("python",     "code"),
    ".js":   ("javascript", "code"),
    ".ts":   ("typescript", "code"),
    ".tsx":  ("typescript", "code"),
    ".jsx":  ("javascript", "code"),
    ".java": ("java",       "code"),
    ".go":   ("go",         "code"),
    ".rs":   ("rust",       "code"),
    ".rb":   ("ruby",       "code"),
    ".cpp":  ("cpp",        "code"),
    ".c":    ("c",          "code"),
    ".h":    ("c",          "code"),
    ".hpp":  ("cpp",        "code"),
    ".cs":   ("csharp",     "code"),
    ".md":   ("markdown",   "markdown"),
    ".rst":  ("rst",        "markdown"),
    ".txt":  ("text",       "markdown"),
}


def load_github(url: str) -> list[LoaderResult]:
    """
    Shallow-clone a GitHub repository, walk the file tree,
    and return a LoaderResult for each supported file.

    The temp directory is cleaned up automatically after processing.
    """
    tmp_dir = tempfile.mkdtemp(prefix="codelens_")

    try:
        _clone_repo(url, tmp_dir)
        repo_name = _extract_repo_name(url)
        return _walk_and_collect(Path(tmp_dir), repo_name)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _clone_repo(url: str, dest: str) -> None:
    """Shallow clone (depth=1) to avoid downloading full history."""
    clone_url = url.rstrip("/")
    if not clone_url.endswith(".git"):
        clone_url += ".git"

    subprocess.run(
        ["git", "clone", "--depth", "1", clone_url, dest],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )


def _extract_repo_name(url: str) -> str:
    """'https://github.com/user/repo' → 'user/repo'"""
    url = url.rstrip("/").removesuffix(".git")
    parts = url.split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return parts[-1]


def _walk_and_collect(root: Path, repo_name: str) -> list[LoaderResult]:
    """Walk the cloned repo tree and collect supported files."""
    results = []

    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue

        # Skip files inside ignored directories
        if any(part in _SKIP_DIRS for part in file_path.parts):
            continue

        # Skip unsupported extensions
        ext = file_path.suffix.lower()
        if ext not in _EXTENSION_MAP:
            continue

        # Skip files larger than the configured limit
        if file_path.stat().st_size > settings.max_file_size_bytes:
            continue

        language, doc_type = _EXTENSION_MAP[ext]

        try:
            raw_text = file_path.read_text(encoding="utf-8", errors="ignore")
        except (PermissionError, OSError):
            continue

        # Skip empty files
        if not raw_text.strip():
            continue

        relative_path = str(file_path.relative_to(root)).replace("\\", "/")

        results.append(LoaderResult(
            repository=repo_name,
            file_path=relative_path,
            language=language,
            document_type=doc_type,
            raw_text=raw_text,
        ))

    return results
