-- Migration 019: Ensure processing_queue has a stage column for queue helpers
-- Adds the missing stage column so queue entries can be labeled by pipeline stage.

ALTER TABLE krai_system.processing_queue
ADD COLUMN IF NOT EXISTS stage VARCHAR(50) NOT NULL DEFAULT 'storage';

COMMENT ON COLUMN krai_system.processing_queue.stage IS 'Pipeline stage that enqueued this record';
