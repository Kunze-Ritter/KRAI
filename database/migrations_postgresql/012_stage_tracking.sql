-- =============================================
-- Migration 012: Stage Tracking Table
-- Description: Create krai_system.stage_tracking with stage_number support,
--              indexes, comments, and migration tracking entry.
-- Created: 2026-02-10
-- Reference: Tech Plan specification
-- =============================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS krai_system;

CREATE TABLE IF NOT EXISTS krai_system.stage_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL,
    stage_number INTEGER NOT NULL,
    stage_name VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_stage_tracking_document
        FOREIGN KEY (document_id)
        REFERENCES krai_core.documents(id)
        ON DELETE CASCADE,
    CONSTRAINT uq_stage_tracking_document_stage
        UNIQUE (document_id, stage_number)
);

CREATE INDEX IF NOT EXISTS idx_stage_tracking_document
    ON krai_system.stage_tracking(document_id);

CREATE INDEX IF NOT EXISTS idx_stage_tracking_status
    ON krai_system.stage_tracking(status);

COMMENT ON TABLE krai_system.stage_tracking IS 'Tracks pipeline stage execution per document';
COMMENT ON COLUMN krai_system.stage_tracking.id IS 'Primary key for stage tracking record';
COMMENT ON COLUMN krai_system.stage_tracking.document_id IS 'References krai_core.documents(id)';
COMMENT ON COLUMN krai_system.stage_tracking.stage_number IS 'Numeric stage identifier in processing pipeline';
COMMENT ON COLUMN krai_system.stage_tracking.stage_name IS 'Human-readable stage name';
COMMENT ON COLUMN krai_system.stage_tracking.status IS 'Current stage status (pending, running, completed, failed)';
COMMENT ON COLUMN krai_system.stage_tracking.started_at IS 'Timestamp when stage execution started';
COMMENT ON COLUMN krai_system.stage_tracking.completed_at IS 'Timestamp when stage execution completed';
COMMENT ON COLUMN krai_system.stage_tracking.error_message IS 'Error details if stage execution failed';
COMMENT ON COLUMN krai_system.stage_tracking.metadata IS 'Additional stage metadata as JSON';
COMMENT ON COLUMN krai_system.stage_tracking.created_at IS 'Record creation timestamp';
COMMENT ON COLUMN krai_system.stage_tracking.updated_at IS 'Record last update timestamp';

CREATE TABLE IF NOT EXISTS krai_system.migrations (
    migration_name VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    description TEXT
);

INSERT INTO krai_system.migrations (migration_name, applied_at, description)
VALUES (
    '012_stage_tracking',
    NOW(),
    'Add stage_tracking table with stage_number and indexes'
)
ON CONFLICT (migration_name) DO NOTHING;
