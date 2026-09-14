# CodeLens — AI Developer Knowledge Assistant

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3-06B6D4?logo=tailwindcss&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

An AI-powered developer knowledge assistant that indexes GitHub repositories, documentation websites, and Markdown docs, then answers natural-language questions with grounded, cited responses.

Built with **Advanced RAG** (Retrieval-Augmented Generation) — not just basic vector search, but a multi-stage pipeline combining hybrid retrieval (RRF), cross-encoder re-ranking, confidence gating, AST-aware code chunking, and LLM-powered query autocorrect. Each stage is independently benchmarked to prove it improves answer quality.

---

## ✨ Features

- 🔍 **Hybrid Search** — Combines vector similarity (pgvector) with keyword matching (tsvector) using Reciprocal Rank Fusion
- 🎯 **Cross-Encoder Re-ranking** — ms-marco MiniLM re-scores results for precision
- 🛡️ **Confidence Gating** — Rejects low-quality retrievals instead of hallucinating
- 🧬 **AST-Aware Code Chunking** — Splits Python files at function/class boundaries, not arbitrary line counts
- 📦 **Parent-Child Chunks** — Retrieves focused child chunks but reconstructs full parent context for the LLM
- ⚡ **Redis Caching** — Caches repeated queries with graceful degradation if Redis is down
- 🔄 **SHA-256 Deduplication** — Re-ingesting a repo skips unchanged files automatically
- 🌐 **Multi-Source Ingestion** — GitHub repos, documentation websites, and local Markdown files
- 🧠 **LLM Query Autocorrect** — Fixes typos in user queries before embedding to prevent retrieval failures
- 🖥️ **Modern Chat UI** — Dark-mode frontend built with Alpine.js and Tailwind CSS, with inline source citations
- 🗑️ **Repository Management** — List, filter, and delete indexed data sources via API and UI
- 📊 **Query Audit Logging** — Every query is logged with retrieval IDs, confidence scores, and latency breakdowns

---

## 🏗️ System Architecture

```mermaid
graph LR
    subgraph Frontend
        A["Browser<br>Alpine.js + Tailwind CSS"]
    end

    subgraph API["FastAPI Server"]
        B["/ingest"]
        C["/ask"]
        D["/repositories"]
    end

    subgraph Data["Data Layer"]
        E[("PostgreSQL 16<br>+ pgvector")]
        F[("Redis 7<br>Response Cache")]
    end

    subgraph AI["AI Models"]
        G["all-MiniLM-L6-v2<br>Embedder (384d)"]
        H["ms-marco-MiniLM<br>Cross-Encoder"]
        I["Gemini 3.6 Flash<br>LLM"]
    end

    A -- "HTTP" --> B
    A -- "HTTP" --> C
    A -- "HTTP" --> D
    B --> G
    B --> E
    C --> G
    C --> H
    C --> I
    C --> E
    C --> F
    D --> E
```

---

## 📥 Ingestion Pipeline

How CodeLens processes and stores a new data source:

```mermaid
flowchart TD
    A["POST /ingest<br>{ source_type, url }"] --> B{Source Type?}

    B -->|github| C["git clone --depth 1<br>to temp directory"]
    C --> C1["Walk file tree<br>Skip: .git, node_modules, venv"]
    C1 --> C2["Filter by extension<br>.py .js .ts .md .go .rs ..."]
    C2 --> C3["Enforce size limit<br>< 500 KB per file"]
    C3 --> D

    B -->|web| W["trafilatura.fetch_url()"]
    W --> W1["Extract clean text<br>Strip nav, ads, boilerplate"]
    W1 --> D

    D["List of LoaderResults"] --> E{Language?}

    E -->|Python| F["AST Code Chunker<br>ast.parse()"]
    F --> F1["Parent: full file (__root__)"]
    F --> F2["Children: each function/class<br>with imports prepended"]

    E -->|Markdown| G["Markdown Chunker<br>Heading regex"]
    G --> G1["Parent: full document"]
    G --> G2["Children: each ## section"]

    E -->|Other| H["Fallback Chunker<br>Token window"]
    H --> H1["Parent: full file"]
    H --> H2["Children: 500-token windows<br>with 50-token overlap"]

    F1 & F2 & G1 & G2 & H1 & H2 --> I["SHA-256 Hash<br>per chunk"]

    I --> J{Chunk exists<br>in DB?}
    J -->|"Same hash"| K["Skip<br>(deduplicated)"]
    J -->|"Different hash"| L["Update in-place"]
    J -->|"New"| M["Embed child chunks<br>MiniLM-L6-v2 → 384d vector"]
    M --> N["INSERT into PostgreSQL<br>with parent_id foreign key"]
    L --> N
```

---

## 🔎 Query Pipeline

How CodeLens answers a question end-to-end:

```mermaid
flowchart TD
    A["POST /ask<br>{ query, repo_filter? }"] --> B{"Redis Cache<br>Lookup"}

    B -->|"HIT"| B1["Return cached response<br>+ log audit"]

    B -->|"MISS"| C["LLM Autocorrect<br>Fix typos in query"]
    C --> D["Embed Query<br>MiniLM-L6-v2 → 384d"]

    D --> E["Hybrid Search<br>(PostgreSQL)"]

    E --> E1["Vector CTE<br>cosine distance on HNSW index"]
    E --> E2["Keyword CTE<br>tsvector ts_rank_cd"]
    E1 & E2 --> E3["RRF Fusion<br>score = 1/(k+vRank) + 1/(k+kRank)"]
    E3 --> E4{"Results<br>found?"}
    E4 -->|"No"| X["Return: no relevant information found"]

    E4 -->|"Yes"| F["Cross-Encoder Rerank<br>ms-marco-MiniLM → top 5"]
    F --> G{"Confidence Gate<br>top_score > threshold?"}
    G -->|"Fail"| X

    G -->|"Pass"| H["Parent Context<br>Reconstruction"]
    H --> H1["Batch fetch parent chunks<br>by parent_id"]
    H1 --> H2["Group children<br>under parent file context"]

    H2 --> I["Prompt Assembly"]
    I --> I1["System: answer from context only,<br>cite sources, no hallucination"]
    I --> I2["User: query + labeled<br>[Source: repo — file] blocks"]

    I1 & I2 --> J["LLM Generation<br>Gemini 3.6 Flash<br>temp=0.1, 30s timeout"]

    J --> K["Cache Write<br>Redis TTL 1hr"]
    K --> L["Audit Log<br>query_logs table"]
    L --> M["Return Response<br>{answer, sources,<br>confidence, latency_ms}"]
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **API** | FastAPI (Python 3.11+) |
| **Database** | PostgreSQL 16 + pgvector (HNSW index) |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2, 384d) |
| **Re-ranking** | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| **Cache** | Redis 7 |
| **LLM** | Gemini / OpenAI / Anthropic (provider-agnostic) |
| **Frontend** | Alpine.js + Tailwind CSS + marked.js |
| **Web Scraping** | trafilatura |
| **Containerization** | Docker Compose (PostgreSQL + Redis) |

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/Anuj0725/CodeLens.git
cd CodeLens

# 2. Create virtual environment
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start Postgres + Redis
docker compose up -d

# 5. Configure
cp .env.example .env
# Edit .env — add your Gemini API key (get one at https://aistudio.google.com/apikey)

# 6. Run the API server
uvicorn codelens.api.main:app --reload

# 7. Open the UI
# Open frontend/index.html in your browser
```

---

## 📡 API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/ingest` | Index a GitHub repo or website |
| `POST` | `/ask` | Query the knowledge base |
| `GET` | `/repositories` | List all indexed data sources |
| `DELETE` | `/repositories/{path}` | Delete an indexed data source |

### POST /ingest

Index a GitHub repository:
```json
{
  "source_type": "github",
  "url": "https://github.com/pallets/markupsafe"
}
```

Index a website:
```json
{
  "source_type": "web",
  "url": "https://en.wikipedia.org/wiki/Data_structure"
}
```

### POST /ask
```json
{
  "query": "How does the Markup class escape HTML?",
  "repo_filter": "pallets/markupsafe"
}
```

**Response:**
```json
{
  "answer": "The `escape()` function converts special HTML characters...",
  "confidence_score": -0.78,
  "sources": [
    {"file_path": "src/markupsafe/__init__.py", "chunk_identifier": "escape"},
    {"file_path": "README.md", "chunk_identifier": "## Examples"}
  ],
  "cache_hit": false,
  "latency_ms": {"retrieval": 42, "rerank": 105, "generation": 2937, "total": 3200}
}
```

### GET /repositories
```json
{
  "repositories": [
    "pallets/markupsafe",
    "https://en.wikipedia.org/wiki/Data_structure"
  ]
}
```

### DELETE /repositories/{path}
```json
{
  "message": "Successfully deleted pallets/markupsafe",
  "chunks_deleted": 115
}
```

---

## 📊 Benchmark Results

Evaluated on 25 hand-labeled questions against `pallets/markupsafe` (115 chunks), covering code-specific, conceptual, and exact-match query types:

| Metric | Keyword | Vector | Hybrid | Hybrid+Rerank |
|--------|---------|--------|--------|---------------|
| Precision@5 | 0.000 | 0.080 | 0.080 | **0.096** |
| Recall@5 | 0.000 | 0.320 | 0.320 | **0.400** |
| MRR | 0.000 | 0.291 | 0.289 | **0.361** |

Each pipeline stage adds measurable value: pure keyword search fails entirely on natural-language questions. Vector search establishes a baseline. Hybrid RRF maintains vector quality while adding keyword coverage. The cross-encoder reranker delivers the largest single improvement — **+25% Recall@5** and **+24% MRR** over raw hybrid results, especially on exact-match queries (Recall@5: 0.60).

---

## 📁 Project Structure

```
CodeLens/
├── codelens/
│   ├── api/              # FastAPI endpoints (health, ingest, ask, repos)
│   ├── cache/            # Redis response cache + query audit logger
│   ├── chunking/         # AST code, markdown, and fallback chunkers
│   ├── generation/       # LLM client (multi-provider) + prompt builder
│   ├── indexing/         # Embedder, SHA-256 hasher, ingestion pipeline
│   ├── loaders/          # GitHub, web, and markdown file loaders
│   ├── retrieval/        # Hybrid search, cross-encoder reranker, confidence gate
│   ├── config.py         # Pydantic settings from .env
│   ├── database.py       # asyncpg connection pool
│   └── query_engine.py   # End-to-end RAG pipeline orchestrator
├── frontend/
│   ├── index.html        # Chat UI (Alpine.js + Tailwind CSS)
│   ├── app.js            # Frontend logic and API integration
│   └── style.css         # Custom dark theme overrides
├── eval/
│   ├── test_questions.json  # 25 labeled evaluation questions
│   └── benchmark.py         # Retrieval quality benchmark
├── sql/
│   ├── schema.sql        # PostgreSQL + pgvector table definitions
│   └── rrf.sql           # Standalone RRF query reference
├── tests/                # Unit tests (pytest)
├── docker-compose.yml    # PostgreSQL + Redis containers
└── requirements.txt
```

---

## 🧪 Testing

```bash
pytest tests/ -v
```

---

<div align="center">

### 👨‍💻 Author

**Anuj Madhani**

Built as a deep-dive into production RAG systems — from AST-aware chunking to cross-encoder reranking.

[![GitHub](https://img.shields.io/badge/GitHub-Anuj0725-181717?logo=github&logoColor=white)](https://github.com/Anuj0725)

---

📄 Licensed under **MIT** · © 2026 Anuj Madhani

</div>
