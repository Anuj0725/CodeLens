# CodeLens — AI Developer Knowledge Assistant

An AI-powered developer knowledge assistant that indexes GitHub repositories, documentation websites, and Markdown docs, then answers natural-language questions with grounded, cited responses.

Built with **Advanced RAG** (Retrieval-Augmented Generation): hybrid search (RRF), cross-encoder re-ranking, confidence gating, and AST-aware code chunking.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI (Python 3.11+) |
| Database | PostgreSQL 16 + pgvector |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Re-ranking | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| Cache | Redis |
| LLM | OpenAI / Anthropic API |

## Status

🚧 Under development

## Setup

_Coming soon_

## License

MIT
