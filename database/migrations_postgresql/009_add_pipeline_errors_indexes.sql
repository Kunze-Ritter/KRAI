-- Migration: Add indexes to pipeline_errors table for optimized error monitoring queries
-- Created: 2026-01-14
-- Purpose: Improve performance of error monitoring widgets by adding indexes on frequently queried columns

-- Index for filtering by status and ordering by created_at (used by active(), retrying() scopes)
CREATE INDEX IF NOT EXISTS idx_pipeline_errors_status_created_at
ON krai_system.pipeline_errors (status, created_at DESC);

-- Index for filtering resolved errors by resolved_at timestamp (used by resolved() scope with date filtering)
CREATE INDEX IF NOT EXISTS idx_pipeline_errors_resolved_at
ON krai_system.pipeline_errors (resolved_at DESC)
WHERE resolved_at IS NOT NULL;

-- Index for filtering by error_type for categorization queries
CREATE INDEX IF NOT EXISTS idx_pipeline_errors_error_type
ON krai_system.pipeline_errors (error_type);

-- Index for document_id foreign key lookups (used in eager loading)
CREATE INDEX IF NOT EXISTS idx_pipeline_errors_document_id
ON krai_system.pipeline_errors (document_id);

-- Composite index for stage-based error filtering
CREATE INDEX IF NOT EXISTS idx_pipeline_errors_stage_status
ON krai_system.pipeline_errors (stage, status);

-- Comment on indexes
COMMENT ON INDEX krai_system.idx_pipeline_errors_status_created_at IS
'Optimizes queries filtering by status and ordering by creation date for error monitoring widgets';

COMMENT ON INDEX krai_system.idx_pipeline_errors_resolved_at IS
'Optimizes queries for resolved errors within time ranges (e.g., last 24 hours)';

COMMENT ON INDEX krai_system.idx_pipeline_errors_error_type IS
'Enables fast filtering and grouping by error type for analytics';

COMMENT ON INDEX krai_system.idx_pipeline_errors_document_id IS
'Improves performance of joins with documents table in error listings';

COMMENT ON INDEX krai_system.idx_pipeline_errors_stage_status IS
'Optimizes queries filtering errors by processing stage and status';
