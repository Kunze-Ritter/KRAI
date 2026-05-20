-- ======================================================================
-- KRAI PostgreSQL Database - Manufacturer Verification Cache
-- ======================================================================
-- Version: 1.0
-- Created: 2025-12-21
-- Description: Cache table for web-based manufacturer verification results
--              Stores verification data from Firecrawl searches to minimize API calls
-- ======================================================================

-- ======================================================================
-- MANUFACTURER VERIFICATION CACHE TABLE
-- ======================================================================

CREATE TABLE IF NOT EXISTS krai_intelligence.manufacturer_verification_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    verification_type VARCHAR(50) NOT NULL,  -- 'manufacturer', 'model', 'parts', 'specs'
    cache_key VARCHAR(255) NOT NULL UNIQUE,  -- hash of (type, manufacturer, model)
    manufacturer VARCHAR(255),
    model_number VARCHAR(255),
    verification_data JSONB NOT NULL,
    confidence FLOAT,
    source_url TEXT,
    cached_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    cache_valid_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ======================================================================
-- INDEXES
-- ======================================================================

CREATE INDEX IF NOT EXISTS idx_verification_cache_key
    ON krai_intelligence.manufacturer_verification_cache(cache_key);

CREATE INDEX IF NOT EXISTS idx_verification_cache_valid
    ON krai_intelligence.manufacturer_verification_cache(cache_valid_until);

CREATE INDEX IF NOT EXISTS idx_verification_type
    ON krai_intelligence.manufacturer_verification_cache(verification_type);

CREATE INDEX IF NOT EXISTS idx_verification_manufacturer
    ON krai_intelligence.manufacturer_verification_cache(manufacturer);

CREATE INDEX IF NOT EXISTS idx_verification_model
    ON krai_intelligence.manufacturer_verification_cache(model_number);

-- ======================================================================
-- COMMENTS
-- ======================================================================

COMMENT ON TABLE krai_intelligence.manufacturer_verification_cache IS
    'Cache for web-based manufacturer verification results from Firecrawl searches';

COMMENT ON COLUMN krai_intelligence.manufacturer_verification_cache.verification_type IS
    'Type of verification: manufacturer, model, parts, or specs';

COMMENT ON COLUMN krai_intelligence.manufacturer_verification_cache.cache_key IS
    'SHA256 hash of verification parameters for unique identification';

COMMENT ON COLUMN krai_intelligence.manufacturer_verification_cache.verification_data IS
    'JSON data containing verification results';

COMMENT ON COLUMN krai_intelligence.manufacturer_verification_cache.confidence IS
    'Confidence score (0.0-1.0) of the verification result';

COMMENT ON COLUMN krai_intelligence.manufacturer_verification_cache.cache_valid_until IS
    'Timestamp when cache entry expires (default: 90 days from creation)';

-- ======================================================================
-- MIGRATION TRACKING
-- ======================================================================

INSERT INTO krai_system.migrations (migration_name, description)
VALUES (
    '004_manufacturer_verification_cache',
    'Added manufacturer_verification_cache table for web-based verification caching'
)
ON CONFLICT (migration_name) DO NOTHING;
