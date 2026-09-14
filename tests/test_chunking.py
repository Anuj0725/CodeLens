import pytest
from codelens.loaders.base import LoaderResult
from codelens.chunking.markdown_chunker import chunk_markdown
from codelens.chunking.code_chunker import chunk_python_code
from codelens.chunking.fallback_chunker import chunk_fallback


def _make_loader_result(text, lang="python", doc_type="code"):
    return LoaderResult(
        repository="test/repo",
        file_path="test_file.py",
        language=lang,
        document_type=doc_type,
        raw_text=text,
    )


class TestMarkdownChunker:
    def test_splits_by_headings(self):
        md = "# Title\nSome longer introductory text goes here.\n## Subtitle\nMore details here about the topic."
        lr = _make_loader_result(md, lang="markdown", doc_type="markdown")
        chunks = chunk_markdown(lr)
        # Should have parent + 2 children (Title section, Subtitle section)
        assert len(chunks) >= 3
        assert chunks[0].chunk_type == "parent"
        children = [c for c in chunks if c.chunk_type == "child"]
        identifiers = [c.chunk_identifier for c in children]
        assert any("Title" in i for i in identifiers)
        assert any("Subtitle" in i for i in identifiers)

    def test_empty_text_returns_nothing(self):
        lr = _make_loader_result("", lang="markdown", doc_type="markdown")
        assert chunk_markdown(lr) == []

    def test_no_headings_returns_parent_only(self):
        lr = _make_loader_result("Just plain text, no headings.", lang="markdown", doc_type="markdown")
        chunks = chunk_markdown(lr)
        assert len(chunks) == 1
        assert chunks[0].chunk_type == "parent"


class TestCodeChunker:
    def test_extracts_functions_and_classes(self):
        code = "import os\n\ndef my_func():\n    return 42\n\nclass MyClass:\n    pass\n"
        lr = _make_loader_result(code)
        chunks = chunk_python_code(lr)
        assert chunks[0].chunk_type == "parent"
        children = [c for c in chunks if c.chunk_type == "child"]
        identifiers = [c.chunk_identifier for c in children]
        assert "my_func" in identifiers
        assert "MyClass" in identifiers

    def test_empty_file_returns_nothing(self):
        lr = _make_loader_result("")
        assert chunk_python_code(lr) == []


class TestFallbackChunker:
    def test_small_text_returns_parent_only(self):
        lr = _make_loader_result("short text", doc_type="code")
        chunks = chunk_fallback(lr, max_tokens=1000, overlap=50)
        assert len(chunks) == 1
        assert chunks[0].chunk_type == "parent"

    def test_large_text_splits_into_children(self):
        # 500 words > max_tokens=100
        big_text = " ".join(["word"] * 500)
        lr = _make_loader_result(big_text, doc_type="code")
        chunks = chunk_fallback(lr, max_tokens=100, overlap=20)
        assert len(chunks) > 2  # parent + multiple children
        assert chunks[0].chunk_type == "parent"
        assert all(c.chunk_type == "child" for c in chunks[1:])
