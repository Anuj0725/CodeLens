CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Core table: stores both parent and child chunks in one table.
-- Parent chunks hold full context (entire file/section).
-- Child chunks are the retrieval targets (functions, headings).
-- ============================================================
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id               UUID REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    repository              TEXT NOT NULL,
    file_path               TEXT,
    chunk_identifier        TEXT,
    language                TEXT,
    document_type           TEXT NOT NULL CHECK (document_type IN ('code', 'markdown', 'docs_site', 'blog')),
    chunk_type              TEXT NOT NULL CHECK (chunk_type IN ('parent', 'child')),
    chunk_text              TEXT NOT NULL,
    content_hash            TEXT NOT NULL,
    embedding_model_version TEXT,
    embedding               vector(384),
    tsvector_content        tsvector GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Upsert dedup: find existing chunk by its position in source
CREATE UNIQUE INDEX IF NOT EXISTS idx_chunks_upsert_key
    ON chunks (repository, file_path, chunk_identifier, chunk_type);

-- Vector similarity search (use HNSW for small datasets — no minimum row requirement unlike IVFFlat)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON chunks USING hnsw (embedding vector_cosine_ops);

-- Full-text keyword search
CREATE INDEX IF NOT EXISTS idx_chunks_tsvector
    ON chunks USING GIN (tsvector_content);

-- Content hash lookup for dedup checks
CREATE INDEX IF NOT EXISTS idx_chunks_content_hash
    ON chunks (content_hash);

-- Repository filtering on queries
CREATE INDEX IF NOT EXISTS idx_chunks_repository
    ON chunks (repository);

-- Parent lookup during context reconstruction
CREATE INDEX IF NOT EXISTS idx_chunks_parent_id
    ON chunks (parent_id);


-- ============================================================
-- Query audit log: every query gets logged with latencies
-- and retrieved chunk IDs for debugging and evaluation.
-- ============================================================
CREATE TABLE IF NOT EXISTS query_logs (
    log_id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text              TEXT NOT NULL,
    retrieved_chunk_ids     UUID[],
    reranked_chunk_ids      UUID[],
    confidence_score        FLOAT,
    cache_hit               BOOLEAN NOT NULL DEFAULT false,
    retrieval_latency_ms    INT,
    rerank_latency_ms       INT,
    generation_latency_ms   INT,
    total_latency_ms        INT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
