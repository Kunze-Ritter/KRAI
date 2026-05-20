-- ======================================================================
-- Migration 015: Ensure Retry Policies Table and Defaults
-- ======================================================================
-- Description:
--   Repairs environments where krai_system.retry_policies is missing and
--   seeds idempotent default policies used by RetryPolicyManager.
--   Adds service-level default policy plus TableProcessor stage override.
-- Safe to run:
--   Yes. Uses IF NOT EXISTS and ON CONFLICT for idempotency.
-- ======================================================================

CREATE TABLE IF NOT EXISTS krai_system.retry_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    policy_name VARCHAR(100) UNIQUE NOT NULL,
    service_name VARCHAR(50) NOT NULL,
    stage_name VARCHAR(50),
    max_retries INTEGER NOT NULL DEFAULT 3,
    base_delay_seconds NUMERIC(5,2) NOT NULL DEFAULT 1.0,
    max_delay_seconds NUMERIC(5,2) NOT NULL DEFAULT 60.0,
    exponential_base NUMERIC(3,2) NOT NULL DEFAULT 2.0,
    jitter_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    circuit_breaker_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    circuit_breaker_threshold INTEGER NOT NULL DEFAULT 5,
    circuit_breaker_timeout_seconds INTEGER NOT NULL DEFAULT 60,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_retry_policies_service
    ON krai_system.retry_policies(service_name);

CREATE INDEX IF NOT EXISTS idx_retry_policies_service_stage
    ON krai_system.retry_policies(service_name, stage_name);

INSERT INTO krai_system.retry_policies (
    policy_name,
    service_name,
    stage_name,
    max_retries,
    base_delay_seconds,
    max_delay_seconds,
    exponential_base,
    jitter_enabled,
    circuit_breaker_enabled,
    circuit_breaker_threshold,
    circuit_breaker_timeout_seconds
) VALUES
    ('firecrawl_default', 'firecrawl', NULL, 3, 2.0, 60.0, 2.0, TRUE, FALSE, 5, 60),
    ('database_default', 'database', NULL, 5, 1.0, 30.0, 2.0, TRUE, FALSE, 5, 60),
    ('ollama_default', 'ollama', NULL, 3, 2.0, 120.0, 2.5, TRUE, FALSE, 5, 60),
    ('minio_default', 'minio', NULL, 4, 1.5, 45.0, 2.0, TRUE, FALSE, 5, 60),
    ('system_default', 'default', NULL, 3, 1.0, 60.0, 2.0, TRUE, FALSE, 5, 60),
    ('default_table_processor', 'default', 'TableProcessor', 3, 1.0, 60.0, 2.0, TRUE, FALSE, 5, 60)
ON CONFLICT (policy_name) DO UPDATE SET
    service_name = EXCLUDED.service_name,
    stage_name = EXCLUDED.stage_name,
    max_retries = EXCLUDED.max_retries,
    base_delay_seconds = EXCLUDED.base_delay_seconds,
    max_delay_seconds = EXCLUDED.max_delay_seconds,
    exponential_base = EXCLUDED.exponential_base,
    jitter_enabled = EXCLUDED.jitter_enabled,
    circuit_breaker_enabled = EXCLUDED.circuit_breaker_enabled,
    circuit_breaker_threshold = EXCLUDED.circuit_breaker_threshold,
    circuit_breaker_timeout_seconds = EXCLUDED.circuit_breaker_timeout_seconds,
    updated_at = CURRENT_TIMESTAMP;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'krai_system'
          AND table_name = 'migrations'
    ) THEN
        INSERT INTO krai_system.migrations (migration_name, description)
        VALUES (
            '015_ensure_retry_policies',
            'Ensured krai_system.retry_policies exists and seeded default retry policies including default/TableProcessor'
        )
        ON CONFLICT (migration_name) DO NOTHING;
    END IF;
END $$;
