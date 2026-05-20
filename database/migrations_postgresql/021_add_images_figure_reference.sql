-- ======================================================================
-- Migration 021: Add figure_reference column to krai_content.images
-- ======================================================================
-- Description: figure_reference was added to ImageModel (data_models.py)
--              and populated by image_processor.py via context_extraction_service
--              but was omitted from migration 013 that added the other context
--              columns.  Its absence caused "column does not exist" errors during
--              every image persist that had a figure reference extracted.
-- Safe to run: ADD COLUMN IF NOT EXISTS is idempotent.
-- ======================================================================

ALTER TABLE krai_content.images
    ADD COLUMN IF NOT EXISTS figure_reference TEXT;

COMMENT ON COLUMN krai_content.images.figure_reference IS
    'Figure label extracted from surrounding text, e.g. "Fig. 1.2" or "Figure 3-2".';
