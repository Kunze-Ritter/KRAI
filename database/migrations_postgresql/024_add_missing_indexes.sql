-- ======================================================================
-- Migration 024: Add missing indexes for queue processing and JSONB queries
-- ======================================================================
-- Created: 2026-03-05
-- Description: Performance optimization indexes for processing_queue,
--              videos.metadata, and composite queries
-- ======================================================================

-- ======================================================================
-- PROCESSING_QUEUE INDEXES
-- ======================================================================

-- Index for chunk references in queue
CREATE INDEX IF NOT EXISTS idx_queue_chunk_id
    ON krai_system.processing_queue(chunk_id);

-- Index for image references in queue
CREATE INDEX IF NOT EXISTS idx_queue_image_id
    ON krai_system.processing_queue(image_id);

-- Index for video references in queue
CREATE INDEX IF NOT EXISTS idx_queue_video_id
    ON krai_system.processing_queue(video_id);

-- Index for task type filtering
CREATE INDEX IF NOT EXISTS idx_queue_task_type
    ON krai_system.processing_queue(task_type);

-- Composite index for common queue queries (status + stage + priority)
CREATE INDEX IF NOT EXISTS idx_queue_status_stage_priority
    ON krai_system.processing_queue(status, stage, priority DESC);

-- Composite index for retry processing (document_id + status)
CREATE INDEX IF NOT EXISTS idx_queue_document_status
    ON krai_system.processing_queue(document_id, status);

-- ======================================================================
-- VIDEOS METADATA GIN INDEX (for JSONB queries)
-- ======================================================================

-- GIN index for videos.metadata JSONB queries
-- Enables: metadata->>'enrichment_error', metadata->>'tags'
CREATE INDEX IF NOT EXISTS idx_videos_metadata_gin
    ON krai_content.videos USING GIN(metadata);

-- ======================================================================
-- LINKS METADATA GIN INDEX
-- ======================================================================

-- GIN index for links.position_data JSONB queries
CREATE INDEX IF NOT EXISTS idx_links_position_data_gin
    ON krai_content.links USING GIN(position_data);

-- GIN index for links.metadata JSONB queries
CREATE INDEX IF NOT EXISTS idx_links_metadata_gin
    ON krai_content.links USING GIN(metadata);

-- ======================================================================
-- DOCUMENTS METADATA GIN INDEX
-- ======================================================================

-- GIN index for documents.metadata JSONB queries
CREATE INDEX IF NOT EXISTS idx_documents_metadata_gin
    ON krai_core.documents USING GIN(metadata);

-- ======================================================================
-- CHUNKS ADDITIONAL INDEXES
-- ======================================================================

-- Index for text_chunk search (full-text search already exists, this is for LIKE queries)
CREATE INDEX IF NOT EXISTS idx_chunks_text_preview
    ON krai_intelligence.chunks(left(text_chunk, 200));

-- Index for document_id + chunk_index ordering
CREATE INDEX IF NOT EXISTS idx_chunks_document_order
    ON krai_intelligence.chunks(document_id, chunk_index);

-- ======================================================================
-- ERROR_CODES HIERARCHY INDEXES (if not already from 018)
-- ======================================================================

-- Additional index for hierarchical queries
CREATE INDEX IF NOT EXISTS idx_error_codes_manufacturer
    ON krai_intelligence.error_codes(manufacturer_id);

-- ======================================================================
-- LOGGING
-- ======================================================================

INSERT INTO krai_system.migrations (migration_name, description)
VALUES ('024_add_missing_indexes', 'Add missing indexes for queue processing and JSONB queries')
ON CONFLICT (migration_name) DO NOTHING;
