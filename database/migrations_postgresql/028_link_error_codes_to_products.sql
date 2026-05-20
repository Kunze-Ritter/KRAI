-- Migration 028: Link error codes to products via product_ids array
-- Error codes are extracted from documents which reference models (text array).
-- We populate product_ids by matching document.models against products.model_number
-- with the same manufacturer_id.

-- Add product_ids column (array of product UUIDs)
ALTER TABLE krai_intelligence.error_codes
    ADD COLUMN IF NOT EXISTS product_ids uuid[] DEFAULT '{}';

-- Populate product_ids from document → models → products join
UPDATE krai_intelligence.error_codes ec
SET product_ids = (
    SELECT ARRAY_AGG(DISTINCT p.id ORDER BY p.id)
    FROM krai_core.documents d
    JOIN krai_core.products p
        ON p.model_number = ANY(d.models)
        AND p.manufacturer_id = ec.manufacturer_id
    WHERE d.id = ec.document_id
)
WHERE ec.document_id IS NOT NULL;

-- Set empty arrays to NULL for cleaner data
UPDATE krai_intelligence.error_codes
SET product_ids = NULL
WHERE product_ids = '{}';

-- Index for fast lookup
CREATE INDEX IF NOT EXISTS idx_error_codes_product_ids
    ON krai_intelligence.error_codes USING GIN (product_ids);

-- Summary
DO $$
DECLARE
    v_linked   integer;
    v_total    integer;
BEGIN
    SELECT COUNT(*) INTO v_total FROM krai_intelligence.error_codes;
    SELECT COUNT(*) INTO v_linked FROM krai_intelligence.error_codes WHERE product_ids IS NOT NULL AND array_length(product_ids, 1) > 0;
    RAISE NOTICE 'Migration 028 complete: % / % error codes linked to products', v_linked, v_total;
END $$;
