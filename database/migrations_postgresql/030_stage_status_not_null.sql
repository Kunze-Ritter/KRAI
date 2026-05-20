-- Migration 030: Enforce non-null stage_status / processing_status on documents.
--
-- The Filament UI and master_pipeline.track_stage_status() both rely on
-- krai_core.documents.stage_status being a JSONB object (never null) and
-- processing_status being a non-empty string. Add the constraints explicitly
-- so future inserts can't bypass the defaults.
--
-- Plan: docs/superpowers/plans/2026-03-25-document-status-and-lifecycle-refactor.md (Task B2)

BEGIN;

UPDATE krai_core.documents
SET stage_status = '{}'::jsonb
WHERE stage_status IS NULL;

UPDATE krai_core.documents
SET processing_status = 'pending'
WHERE processing_status IS NULL OR processing_status = '';

ALTER TABLE krai_core.documents
    ALTER COLUMN stage_status SET DEFAULT '{}'::jsonb,
    ALTER COLUMN stage_status SET NOT NULL,
    ALTER COLUMN processing_status SET DEFAULT 'pending',
    ALTER COLUMN processing_status SET NOT NULL;

COMMIT;
