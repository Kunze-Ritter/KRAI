-- Migration 038: Add part_numbers column to service_tickets
-- Purpose: Extract part numbers from metadata into a dedicated, searchable column

ALTER TABLE krai_pm.service_tickets
    ADD COLUMN IF NOT EXISTS part_numbers TEXT[] DEFAULT '{}';

-- Migrate existing part_numbers from metadata to new column
UPDATE krai_pm.service_tickets
SET part_numbers = CASE
    WHEN jsonb_array_length(metadata->'part_numbers') > 0
    THEN array(SELECT jsonb_array_elements_text(metadata->'part_numbers'))
    ELSE '{}'::TEXT[]
END
WHERE metadata ? 'part_numbers'
AND metadata->'part_numbers' IS NOT NULL;

-- Create index for efficient searching
CREATE INDEX IF NOT EXISTS idx_service_tickets_part_numbers
    ON krai_pm.service_tickets USING GIN (part_numbers);

-- Create index on combination: manufacturer + part_numbers (common query pattern)
CREATE INDEX IF NOT EXISTS idx_service_tickets_mfr_parts
    ON krai_pm.service_tickets (manufacturer_id)
    INCLUDE (part_numbers);

-- Log migration info
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM krai_pm.service_tickets WHERE array_length(part_numbers, 1) > 0;
    RAISE NOTICE 'Migration 038 complete: % tickets with part_numbers populated', v_count;
END $$;
