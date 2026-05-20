-- ======================================================================
-- Migration 013: Add context columns to krai_content.images
-- ======================================================================
-- Description: Adds context_caption and related columns to images table
--              when the DB was created from a minimal schema (e.g. 020_schema)
--              that did not include these columns.
-- Safe to run: Uses IF NOT EXISTS; no-op if columns already exist.
-- ======================================================================

-- Add missing columns to krai_content.images (IF NOT EXISTS supported in PostgreSQL 9.5+)
ALTER TABLE krai_content.images ADD COLUMN IF NOT EXISTS context_caption TEXT;
ALTER TABLE krai_content.images ADD COLUMN IF NOT EXISTS page_header TEXT;
ALTER TABLE krai_content.images ADD COLUMN IF NOT EXISTS surrounding_paragraphs TEXT[];
ALTER TABLE krai_content.images ADD COLUMN IF NOT EXISTS related_error_codes TEXT[];
ALTER TABLE krai_content.images ADD COLUMN IF NOT EXISTS related_products UUID[];
ALTER TABLE krai_content.images ADD COLUMN IF NOT EXISTS related_chunks UUID[];

-- context_embedding: add only if column missing; use extensions.vector or public.vector
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'krai_content' AND table_name = 'images' AND column_name = 'context_embedding'
    ) THEN
        IF EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid WHERE n.nspname = 'extensions' AND t.typname = 'vector') THEN
            ALTER TABLE krai_content.images ADD COLUMN context_embedding extensions.vector(768);
        ELSIF EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid WHERE n.nspname = 'public' AND t.typname = 'vector') THEN
            ALTER TABLE krai_content.images ADD COLUMN context_embedding vector(768);
        END IF;
    END IF;
END $$;
