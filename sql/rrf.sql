WITH vector_results AS (
    SELECT chunk_id, file_path, chunk_identifier, chunk_text, repository,
           language, document_type, parent_id,
           ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) AS vector_rank
    FROM chunks
    WHERE chunk_type = 'child'
      AND ($3::text IS NULL OR repository = $3)
    ORDER BY embedding <=> $1::vector
    LIMIT $4
),
keyword_results AS (
    SELECT chunk_id, file_path, chunk_identifier, chunk_text, repository,
           language, document_type, parent_id,
           ROW_NUMBER() OVER (ORDER BY ts_rank_cd(tsvector_content, websearch_to_tsquery('english', $2)) DESC) AS keyword_rank
    FROM chunks
    WHERE chunk_type = 'child'
      AND tsvector_content @@ websearch_to_tsquery('english', $2)
      AND ($3::text IS NULL OR repository = $3)
    ORDER BY ts_rank_cd(tsvector_content, websearch_to_tsquery('english', $2)) DESC
    LIMIT $4
)
SELECT
    COALESCE(v.chunk_id, k.chunk_id) AS chunk_id,
    COALESCE(v.file_path, k.file_path) AS file_path,
    COALESCE(v.chunk_identifier, k.chunk_identifier) AS chunk_identifier,
    COALESCE(v.chunk_text, k.chunk_text) AS chunk_text,
    COALESCE(v.repository, k.repository) AS repository,
    COALESCE(v.language, k.language) AS language,
    COALESCE(v.document_type, k.document_type) AS document_type,
    COALESCE(v.parent_id, k.parent_id) AS parent_id,
    COALESCE(1.0 / ($5 + v.vector_rank), 0.0) +
    COALESCE(1.0 / ($5 + k.keyword_rank), 0.0) AS rrf_score
FROM vector_results v
FULL OUTER JOIN keyword_results k ON v.chunk_id = k.chunk_id
ORDER BY rrf_score DESC
LIMIT $4
