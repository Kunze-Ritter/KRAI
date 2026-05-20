-- ======================================================================
-- Migration 016: Add context columns to krai_intelligence.structured_tables
-- ======================================================================
-- Description: Adds columns required by TableProcessor and EmbeddingProcessor
--              when DB was initialized from a minimal schema.
-- Safe to run: Uses IF NOT EXISTS; no-op if columns already exist.
-- ======================================================================

ALTER TABLE krai_intelligence.structured_tables
    ADD COLUMN IF NOT EXISTS table_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS caption TEXT,
    ADD COLUMN IF NOT EXISTS context_text TEXT,
    ADD COLUMN IF NOT EXISTS bbox JSONB;
