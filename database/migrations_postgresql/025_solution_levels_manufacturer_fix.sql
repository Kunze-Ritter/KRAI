-- Migration 025: Solution Levels + Manufacturer Fix
--
-- 1. Replace solution_text + requires_technician with 3-level solution columns
-- 2. Populate manufacturer_id for all error_codes via documents table join
-- ----------------------------------------------------------------------------

-- ── 1. Add the three solution-level columns ──────────────────────────────────
ALTER TABLE krai_intelligence.error_codes
    ADD COLUMN IF NOT EXISTS solution_customer_text    TEXT,
    ADD COLUMN IF NOT EXISTS solution_agent_text       TEXT,
    ADD COLUMN IF NOT EXISTS solution_technician_text  TEXT;

-- ── 2. Drop obsolete columns ─────────────────────────────────────────────────
ALTER TABLE krai_intelligence.error_codes
    DROP COLUMN IF EXISTS solution_text,
    DROP COLUMN IF EXISTS requires_technician;

-- ── 3. Fix manufacturer_id (was NULL for all 5601 rows) ───────────────────────
-- Join error_codes → documents → manufacturers with name normalisation.
-- CASE WHEN bridges the mismatch between documents.manufacturer (plain text)
-- and manufacturers.name (canonical with suffixes like "Inc.").
UPDATE krai_intelligence.error_codes ec
SET manufacturer_id = m.id
FROM krai_core.documents d
JOIN krai_core.manufacturers m
  ON m.name = CASE d.manufacturer
    WHEN 'HP Inc.'        THEN 'HP Inc.'
    WHEN 'HP'             THEN 'HP Inc.'
    WHEN 'Hewlett Packard' THEN 'HP Inc.'
    WHEN 'Hewlett-Packard' THEN 'HP Inc.'
    WHEN 'Konica Minolta' THEN 'Konica Minolta, Inc.'
    WHEN 'Konica-Minolta' THEN 'Konica Minolta, Inc.'
    WHEN 'Konica'         THEN 'Konica Minolta, Inc.'
    WHEN 'Minolta'        THEN 'Konica Minolta, Inc.'
    WHEN 'Lexmark'        THEN 'Lexmark'
    WHEN 'Lexmark International' THEN 'Lexmark'
    WHEN 'Canon'          THEN 'Canon Inc.'
    WHEN 'Canon Inc.'     THEN 'Canon Inc.'
    WHEN 'Ricoh'          THEN 'Ricoh Company, Ltd.'
    WHEN 'Ricoh Company'  THEN 'Ricoh Company, Ltd.'
    WHEN 'Xerox'          THEN 'Xerox Holdings'
    WHEN 'Xerox Holdings Corporation' THEN 'Xerox Holdings'
    ELSE d.manufacturer
  END
WHERE ec.document_id = d.id
  AND d.manufacturer IS NOT NULL
  AND ec.manufacturer_id IS NULL;

-- ── 4. Add index for the new columns (for fast lookup) ───────────────────────
CREATE INDEX IF NOT EXISTS idx_error_codes_has_technician_solution
    ON krai_intelligence.error_codes (id)
    WHERE solution_technician_text IS NOT NULL;

-- ── 5. Update the vw_error_codes view (if it exists) ─────────────────────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.views
    WHERE table_schema = 'public' AND table_name = 'vw_error_codes'
  ) THEN
    DROP VIEW public.vw_error_codes;
    CREATE OR REPLACE VIEW public.vw_error_codes AS
    SELECT
        ec.id,
        ec.error_code,
        ec.error_description,
        ec.solution_customer_text,
        ec.solution_agent_text,
        ec.solution_technician_text,
        ec.page_number,
        ec.severity_level,
        ec.confidence_score,
        ec.parent_code,
        ec.is_category,
        ec.manufacturer_id,
        m.name  AS manufacturer_name,
        ec.document_id,
        d.filename AS document_filename,
        d.models   AS document_models
    FROM krai_intelligence.error_codes ec
    LEFT JOIN krai_core.manufacturers m ON ec.manufacturer_id = m.id
    LEFT JOIN krai_core.documents      d ON ec.document_id    = d.id;
  END IF;
END $$;
