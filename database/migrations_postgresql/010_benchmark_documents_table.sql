-- Migration 010: Create benchmark_documents table
-- Purpose: Store selected benchmark documents for performance testing
-- Author: KRAI System
-- Date: 2026-01-22

-- Create benchmark_documents table in krai_system schema
CREATE TABLE IF NOT EXISTS krai_system.benchmark_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL,
    snapshot_id VARCHAR(255) NOT NULL,
    file_size BIGINT,
    selected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Foreign key constraint
    CONSTRAINT fk_benchmark_document
        FOREIGN KEY (document_id)
        REFERENCES krai_core.documents(id)
        ON DELETE CASCADE,

    -- Unique constraint for idempotency
    CONSTRAINT uq_benchmark_document_snapshot
        UNIQUE (document_id, snapshot_id)
);

-- Create indexes for query performance
CREATE INDEX IF NOT EXISTS idx_benchmark_documents_document_id
    ON krai_system.benchmark_documents(document_id);

CREATE INDEX IF NOT EXISTS idx_benchmark_documents_snapshot_id
    ON krai_system.benchmark_documents(snapshot_id);

CREATE INDEX IF NOT EXISTS idx_benchmark_documents_selected_at
    ON krai_system.benchmark_documents(selected_at DESC);

-- Add comment to table
COMMENT ON TABLE krai_system.benchmark_documents IS
    'Stores selected benchmark documents for performance testing and baseline measurements';

COMMENT ON COLUMN krai_system.benchmark_documents.document_id IS
    'Reference to the document in krai_core.documents';

COMMENT ON COLUMN krai_system.benchmark_documents.snapshot_id IS
    'Identifier for the staging snapshot from which this document was selected';

COMMENT ON COLUMN krai_system.benchmark_documents.file_size IS
    'Size of the document file in bytes';

COMMENT ON COLUMN krai_system.benchmark_documents.metadata IS
    'Additional metadata including is_benchmark flag and selection criteria';

-- Insert migration record
INSERT INTO krai_system.migrations (migration_name, applied_at)
VALUES ('010_benchmark_documents_table', NOW())
ON CONFLICT (migration_name) DO NOTHING;

-- Rollback script (run manually if needed):
-- DROP INDEX IF EXISTS krai_system.idx_benchmark_documents_selected_at;
-- DROP INDEX IF EXISTS krai_system.idx_benchmark_documents_snapshot_id;
-- DROP INDEX IF EXISTS krai_system.idx_benchmark_documents_document_id;
-- DROP TABLE IF EXISTS krai_system.benchmark_documents CASCADE;
-- DELETE FROM krai_system.migrations WHERE migration_name = '010_benchmark_documents_table';
