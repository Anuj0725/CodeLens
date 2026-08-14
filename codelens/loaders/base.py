from dataclasses import dataclass


@dataclass
class LoaderResult:
    """
    Uniform output from every loader. One LoaderResult = one source file
    or web page, before any chunking happens.
    """
    repository: str
    file_path: str
    language: str
    document_type: str   # "code", "markdown", "docs_site", "blog"
    raw_text: str
