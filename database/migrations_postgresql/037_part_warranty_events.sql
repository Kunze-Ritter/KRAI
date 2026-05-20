-- Migration 037: Part Warranty Events + Fix predictions.metadata
-- Adds warranty event tracking for part replacements and fixes missing metadata column

-- Bug Fix: predictions.metadata was referenced in prediction_service.py but never created
ALTER TABLE krai_pm.predictions
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::JSONB;

-- Part Warranty Events: Track when parts fail relative to warranty window
CREATE TABLE IF NOT EXISTS krai_pm.part_warranty_events (
    id SERIAL PRIMARY KEY,
    ticket_id VARCHAR(255) REFERENCES krai_pm.service_tickets(id) ON DELETE CASCADE,
    manufacturer_id UUID REFERENCES krai_core.manufacturers(id),
    part_category VARCHAR(50) NOT NULL,
    part_number VARCHAR(100),
    -- Warranty window (typically 365 days from failure date)
    failure_date TIMESTAMP NOT NULL,
    warranty_expiry_date TIMESTAMP,
    is_in_warranty BOOLEAN DEFAULT FALSE,
    -- Lifetime comparison
    nominal_lifetime_pages INTEGER,          -- From part_lifetimes
    actual_runtime_pages INTEGER,            -- Placeholder: Docuware/Radix when available
    mismatch_ratio DECIMAL(10, 4),           -- actual / nominal (< 1.0 = early failure)
    -- Financial impact
    estimated_repair_cost_eur DECIMAL(10, 2),
    -- Warranty claim status
    warranty_status VARCHAR(50) DEFAULT 'unchecked',  -- unchecked, submitted, accepted, rejected, disputed
    -- Extensibility
    metadata JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_warranty_events_manufacturer
    ON krai_pm.part_warranty_events(manufacturer_id);

CREATE INDEX IF NOT EXISTS idx_warranty_events_part_category
    ON krai_pm.part_warranty_events(part_category);

CREATE INDEX IF NOT EXISTS idx_warranty_events_is_in_warranty
    ON krai_pm.part_warranty_events(is_in_warranty);

CREATE INDEX IF NOT EXISTS idx_warranty_events_failure_date
    ON krai_pm.part_warranty_events(failure_date DESC);

CREATE INDEX IF NOT EXISTS idx_warranty_events_ticket_id
    ON krai_pm.part_warranty_events(ticket_id);

-- Analysis view: warranty metrics aggregated by manufacturer + part category
CREATE OR REPLACE VIEW krai_pm.vw_warranty_analysis AS
SELECT
    m.name AS manufacturer_name,
    pwe.part_category,
    COUNT(*) AS total_replacements,
    COUNT(*) FILTER (WHERE pwe.is_in_warranty) AS warranty_eligible_count,
    ROUND(100.0 * COUNT(*) FILTER (WHERE pwe.is_in_warranty)
          / NULLIF(COUNT(*), 0), 2) AS warranty_rate_pct,
    AVG(pwe.nominal_lifetime_pages)::INT AS avg_nominal_lifetime,
    AVG(pwe.actual_runtime_pages)::INT AS avg_actual_runtime,
    ROUND(AVG(pwe.mismatch_ratio)::NUMERIC, 4) AS avg_mismatch_ratio,
    ROUND(SUM(pwe.estimated_repair_cost_eur)::NUMERIC, 2) AS total_repair_cost_eur
FROM krai_pm.part_warranty_events pwe
JOIN krai_core.manufacturers m ON pwe.manufacturer_id = m.id
GROUP BY m.name, pwe.part_category
ORDER BY warranty_eligible_count DESC NULLS LAST, total_repair_cost_eur DESC NULLS LAST;
