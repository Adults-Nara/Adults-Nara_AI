-- PGVector 확장 활성화
CREATE EXTENSION IF NOT EXISTS vector;

-- 영상 임베딩 테이블
CREATE TABLE IF NOT EXISTS video_embedding (
    id          BIGSERIAL PRIMARY KEY,
    video_id    BIGINT NOT NULL UNIQUE,
    summary     TEXT,
    embedding   VECTOR(1536) NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- 코사인 유사도 검색용 HNSW 인덱스
CREATE INDEX IF NOT EXISTS idx_video_embedding_hnsw
    ON video_embedding
    USING hnsw (embedding vector_cosine_ops);

-- 유사 영상 검색 쿼리 (참고용)
-- SELECT video_id, 1 - (embedding <=> target_embedding) AS similarity
-- FROM video_embedding
-- WHERE video_id != :currentVideoId
-- ORDER BY embedding <=> (SELECT embedding FROM video_embedding WHERE video_id = :currentVideoId)
-- LIMIT 10;
