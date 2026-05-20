-- Migration 020: Add extended columns to processing_queue
-- The table was created from an older schema that lacked these columns.
-- The postgresql_adapter.create_svg_queue_entry() method requires all of them.

ALTER TABLE krai_system.processing_queue
    ADD COLUMN IF NOT EXISTS payload       JSONB         DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS chunk_id      UUID,
    ADD COLUMN IF NOT EXISTS image_id      UUID,
    ADD COLUMN IF NOT EXISTS video_id      UUID,
    ADD COLUMN IF NOT EXISTS task_type     VARCHAR(100),
    ADD COLUMN IF NOT EXISTS retry_count   INTEGER       NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_retries   INTEGER       NOT NULL DEFAULT 3,
    ADD COLUMN IF NOT EXISTS updated_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW();

COMMENT ON COLUMN krai_system.processing_queue.payload     IS 'Arbitrary JSON payload for the queued task';
COMMENT ON COLUMN krai_system.processing_queue.chunk_id    IS 'Optional FK to krai_intelligence.chunks';
COMMENT ON COLUMN krai_system.processing_queue.image_id    IS 'Optional FK to krai_content.images';
COMMENT ON COLUMN krai_system.processing_queue.video_id    IS 'Optional FK to krai_content.videos';
COMMENT ON COLUMN krai_system.processing_queue.task_type   IS 'Task type label (e.g. image, video, storage)';
COMMENT ON COLUMN krai_system.processing_queue.retry_count IS 'Number of times this task has been retried';
COMMENT ON COLUMN krai_system.processing_queue.max_retries  IS 'Maximum number of retries allowed';
COMMENT ON COLUMN krai_system.processing_queue.updated_at   IS 'Timestamp of last status update';
