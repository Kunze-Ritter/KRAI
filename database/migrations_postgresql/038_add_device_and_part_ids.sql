-- Migration 038: Add Radix Device IDs and Part IDs for complete traceability
-- Purpose: Link all warranty data back to source systems with internal IDs
-- Created: 2026-05-19

-- Add Radix device ID to service_tickets for traceability
ALTER TABLE krai_pm.service_tickets
    ADD COLUMN IF NOT EXISTS radix_device_id VARCHAR(100),  -- Interne Geräte-ID aus Radix (z.B. "16511")
    ADD COLUMN IF NOT EXISTS device_serial VARCHAR(100);     -- Seriennummer des Geräts

CREATE INDEX IF NOT EXISTS idx_service_tickets_radix_device_id
    ON krai_pm.service_tickets(radix_device_id);

-- Add part IDs to part_lifetimes for handling part number variants
-- Important: Konica Minolta uses different part numbers for same part across revisions
-- Example: AA2JR71700 vs AA2JR71711 = same part, different revision
ALTER TABLE krai_pm.part_lifetimes
    ADD COLUMN IF NOT EXISTS radix_part_id VARCHAR(100),          -- Radix-spezifische Artikel-ID wenn vorhanden
    ADD COLUMN IF NOT EXISTS part_number_variants TEXT[],         -- Array of equivalent part numbers (AA2JR71700, AA2JR71711)
    ADD COLUMN IF NOT EXISTS manufacturer_part_code VARCHAR(100);  -- OEM part code (z.B. "DV711K" für Konica)

CREATE INDEX IF NOT EXISTS idx_part_lifetimes_part_variants
    ON krai_pm.part_lifetimes USING gin(part_number_variants);

-- Add detailed traceability to part_warranty_events
ALTER TABLE krai_pm.part_warranty_events
    ADD COLUMN IF NOT EXISTS radix_device_id VARCHAR(100),    -- Link to source Radix device
    ADD COLUMN IF NOT EXISTS radix_part_id VARCHAR(100),      -- Link to source Radix part
    ADD COLUMN IF NOT EXISTS device_serial VARCHAR(100);      -- Device serial for correlation

CREATE INDEX IF NOT EXISTS idx_warranty_events_radix_device_id
    ON krai_pm.part_warranty_events(radix_device_id);

CREATE INDEX IF NOT EXISTS idx_warranty_events_radix_part_id
    ON krai_pm.part_warranty_events(radix_part_id);

-- Device lifecycle table - add Radix IDs for traceability
ALTER TABLE krai_pm.device_lifecycle
    ADD COLUMN IF NOT EXISTS radix_device_id VARCHAR(100),     -- Interne Geräte-ID aus Radix
    ADD COLUMN IF NOT EXISTS radix_system_id VARCHAR(100);     -- System ID aus Radix Beschreibung

CREATE INDEX IF NOT EXISTS idx_device_lifecycle_radix_ids
    ON krai_pm.device_lifecycle(radix_device_id, radix_system_id);

-- Warranty events view: updated to show device traceability
CREATE OR REPLACE VIEW krai_pm.vw_warranty_analysis_detailed AS
SELECT
    m.name AS manufacturer_name,
    pwe.part_category,
    pwe.radix_device_id,
    pwe.radix_part_id,
    COUNT(*) AS total_replacements,
    COUNT(*) FILTER (WHERE pwe.is_in_warranty) AS warranty_eligible_count,
    ROUND(100.0 * COUNT(*) FILTER (WHERE pwe.is_in_warranty)
          / NULLIF(COUNT(*), 0), 2) AS warranty_rate_pct,
    AVG(pwe.nominal_lifetime_pages)::INT AS avg_nominal_lifetime,
    AVG(pwe.actual_runtime_pages)::INT AS avg_actual_runtime,
    ROUND(AVG(pwe.mismatch_ratio)::NUMERIC, 4) AS avg_mismatch_ratio,
    ROUND(SUM(pwe.estimated_repair_cost_eur)::NUMERIC, 2) AS total_repair_cost_eur,
    STRING_AGG(DISTINCT pwe.device_serial, ', ') AS affected_device_serials
FROM krai_pm.part_warranty_events pwe
JOIN krai_core.manufacturers m ON pwe.manufacturer_id = m.id
GROUP BY m.name, pwe.part_category, pwe.radix_device_id, pwe.radix_part_id
ORDER BY warranty_eligible_count DESC NULLS LAST, total_repair_cost_eur DESC NULLS LAST;

-- Add comments for documentation
COMMENT ON COLUMN krai_pm.service_tickets.radix_device_id IS 'Internal device ID from Radix (z.B. "16511")';
COMMENT ON COLUMN krai_pm.service_tickets.device_serial IS 'Device serial number for correlation with Docuform/device_lifecycle';

COMMENT ON COLUMN krai_pm.part_lifetimes.radix_part_id IS 'Part ID from Radix system for linking to events';
COMMENT ON COLUMN krai_pm.part_lifetimes.part_number_variants IS 'Array of equivalent part numbers (e.g., Konica Minolta revisions: AA2JR71700, AA2JR71711)';
COMMENT ON COLUMN krai_pm.part_lifetimes.manufacturer_part_code IS 'OEM part code (e.g., "DV711K", "A2X203D")';

COMMENT ON COLUMN krai_pm.part_warranty_events.radix_device_id IS 'Source device ID for traceability back to Radix';
COMMENT ON COLUMN krai_pm.part_warranty_events.radix_part_id IS 'Source part ID for traceability back to Radix';

COMMENT ON VIEW krai_pm.vw_warranty_analysis_detailed IS 'Warranty analysis with device and part IDs for complete traceability to source systems';
