import trafilatura

from codelens.loaders.base import LoaderResult


def load_web_page(
    url: str,
    doc_type: str = "docs_site",
) -> list[LoaderResult]:
    """
    Fetch a web page and extract its main text content,
    stripping navigation, ads, and boilerplate HTML.

    Returns a single-element list for consistency with other loaders,
    or an empty list if extraction fails.
    """
    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        return []

    extracted = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
        output_format="txt",
    )

    if not extracted or not extracted.strip():
        return []

    return [
        LoaderResult(
            repository=url,
            file_path=url,
            language="text",
            document_type=doc_type,
            raw_text=extracted,
        )
    ]
