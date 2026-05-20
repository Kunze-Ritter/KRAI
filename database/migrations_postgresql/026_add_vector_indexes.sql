-- ======================================================================
-- Migration 026: Add missing HNSW vector indexes for multimodal search
-- ======================================================================
-- Description: Adds HNSW indexes to videos, links, and structured_tables
--              to optimize similarity search across all document artifacts.
-- ======================================================================

-- Videos Context Embedding Index
CREATE INDEX IF NOT EXISTS idx_videos_context_embedding ON krai_content.videos
    USING hnsw (context_embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Links Context Embedding Index
CREATE INDEX IF NOT EXISTS idx_links_context_embedding ON krai_content.links
    USING hnsw (context_embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Structured Tables Embedding Indexes
CREATE INDEX IF NOT EXISTS idx_tables_table_embedding ON krai_intelligence.structured_tables
    USING hnsw (table_embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_tables_context_embedding ON krai_intelligence.structured_tables
    USING hnsw (context_embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Record migration
INSERT INTO krai_system.migrations (migration_name, applied_at, description)
VALUES ('026_add_vector_indexes', NOW(), 'Add missing HNSW vector indexes for videos, links, and structured_tables')
ON CONFLICT (migration_name) DO NOTHING;
