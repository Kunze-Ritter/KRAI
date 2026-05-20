-- ======================================================================
-- Migration 008: Pipeline Resilience Schema
-- ======================================================================
-- Description: Adds 6 tables to krai_system schema for pipeline resilience,
--              error handling, and observability capabilities
-- Created: 2026-01-12
-- Purpose: Provides database foundation for error tracking, retry policies,
--          alert management, stage completion tracking, and performance baselines
-- Reference: Tech Spec - Pipeline Resilience and Error Handling System
-- ======================================================================

-- ======================================================================
-- Table 1: stage_completion_markers
-- ======================================================================
-- Tracks stage completion with data hashing for idempotency checks

CREATE TABLE IF NOT EXISTS krai_system.stage_completion_markers (
    document_id UUID NOT NULL,
    stage_name VARCHAR(50) NOT NULL,
    completed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_hash VARCHAR(64),
    metadata JSONB,
    PRIMARY KEY (document_id, stage_name)
);

COMMENT ON TABLE krai_system.stage_completion_markers IS 'Tracks stage completion with data hashing for idempotency checks';
COMMENT ON COLUMN krai_system.stage_completion_markers.data_hash IS 'SHA-256 hash of stage output for change detection';
COMMENT ON COLUMN krai_system.stage_completion_markers.metadata IS 'Additional stage-specific metadata';

-- Indexes for stage_completion_markers
CREATE INDEX IF NOT EXISTS idx_completion_markers_document
    ON krai_system.stage_completion_markers(document_id);

CREATE INDEX IF NOT EXISTS idx_completion_markers_stage
    ON krai_system.stage_completion_markers(stage_name);

-- ======================================================================
-- Table 2: pipeline_errors
-- ======================================================================
-- Primary table for error tracking and Dashboard queries

CREATE TABLE IF NOT EXISTS krai_system.pipeline_errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    error_id VARCHAR(100) UNIQUE NOT NULL,
    document_id UUID NOT NULL,
    stage_name VARCHAR(50) NOT NULL,
    error_type VARCHAR(50) NOT NULL,
    error_category VARCHAR(50) NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    context JSONB,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    next_retry_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    severity VARCHAR(20) NOT NULL DEFAULT 'medium',
    is_transient BOOLEAN NOT NULL DEFAULT TRUE,
    correlation_id VARCHAR(100),
    parent_error_id VARCHAR(100),
    stage_status JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_by UUID,
    resolution_notes TEXT,
    CONSTRAINT fk_pipeline_errors_document
        FOREIGN KEY (document_id)
        REFERENCES krai_core.documents(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_pipeline_errors_resolved_by
        FOREIGN KEY (resolved_by)
        REFERENCES krai_users.users(id)
);

COMMENT ON TABLE krai_system.pipeline_errors IS 'Primary table for error tracking and Dashboard queries';
COMMENT ON COLUMN krai_system.pipeline_errors.error_id IS 'Unique identifier for error deduplication';
COMMENT ON COLUMN krai_system.pipeline_errors.error_category IS 'High-level category: network, validation, resource, system';
COMMENT ON COLUMN krai_system.pipeline_errors.is_transient IS 'Whether error is likely to succeed on retry';
COMMENT ON COLUMN krai_system.pipeline_errors.correlation_id IS 'Groups related errors across stages';
COMMENT ON COLUMN krai_system.pipeline_errors.parent_error_id IS 'Links cascading errors to root cause';
COMMENT ON COLUMN krai_system.pipeline_errors.stage_status IS 'Stage-specific status information and metadata';

-- Indexes for pipeline_errors
CREATE INDEX IF NOT EXISTS idx_pipeline_errors_document
    ON krai_system.pipeline_errors(document_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_errors_stage
    ON krai_system.pipeline_errors(stage_name);

CREATE INDEX IF NOT EXISTS idx_pipeline_errors_status
    ON krai_system.pipeline_errors(status);

CREATE INDEX IF NOT EXISTS idx_pipeline_errors_created
    ON krai_system.pipeline_errors(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_pipeline_errors_error_type
    ON krai_system.pipeline_errors(error_type);

CREATE INDEX IF NOT EXISTS idx_pipeline_errors_correlation
    ON krai_system.pipeline_errors(correlation_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_errors_resolved_by
    ON krai_system.pipeline_errors(resolved_by);

-- ======================================================================
-- Table 3: alert_queue
-- ======================================================================
-- Queue for alert aggregation to prevent spam

CREATE TABLE IF NOT EXISTS krai_system.alert_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    details JSONB,
    aggregation_key VARCHAR(200),
    aggregation_count INTEGER NOT NULL DEFAULT 1,
    first_occurrence TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_occurrence TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    sent_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE krai_system.alert_queue IS 'Queue for alert aggregation to prevent spam';
COMMENT ON COLUMN krai_system.alert_queue.aggregation_key IS 'Key for grouping similar alerts';
COMMENT ON COLUMN krai_system.alert_queue.aggregation_count IS 'Number of similar alerts aggregated';

-- Indexes for alert_queue
CREATE INDEX IF NOT EXISTS idx_alert_queue_status
    ON krai_system.alert_queue(status);

CREATE INDEX IF NOT EXISTS idx_alert_queue_aggregation
    ON krai_system.alert_queue(aggregation_key);

CREATE INDEX IF NOT EXISTS idx_alert_queue_created
    ON krai_system.alert_queue(created_at);

-- ======================================================================
-- Table 4: alert_configurations
-- ======================================================================
-- Stores alert rules and recipients configured via Dashboard

CREATE TABLE IF NOT EXISTS krai_system.alert_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    error_types VARCHAR(50)[],
    stages VARCHAR(50)[],
    severity_threshold VARCHAR(20) NOT NULL DEFAULT 'medium',
    error_count_threshold INTEGER NOT NULL DEFAULT 5,
    time_window_minutes INTEGER NOT NULL DEFAULT 15,
    aggregation_window_minutes INTEGER NOT NULL DEFAULT 5,
    email_recipients TEXT[],
    slack_webhooks TEXT[],
    created_by UUID,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alert_configurations_created_by
        FOREIGN KEY (created_by)
        REFERENCES krai_users.users(id)
);

COMMENT ON TABLE krai_system.alert_configurations IS 'Stores alert rules and recipients configured via Dashboard';
COMMENT ON COLUMN krai_system.alert_configurations.error_types IS 'Array of error types to match';
COMMENT ON COLUMN krai_system.alert_configurations.stages IS 'Array of pipeline stages to monitor';
COMMENT ON COLUMN krai_system.alert_configurations.time_window_minutes IS 'Time window for error count threshold';
COMMENT ON COLUMN krai_system.alert_configurations.aggregation_window_minutes IS 'Window for aggregating similar alerts';

-- Indexes for alert_configurations
CREATE INDEX IF NOT EXISTS idx_alert_configurations_created_by
    ON krai_system.alert_configurations(created_by);

-- ======================================================================
-- Table 5: retry_policies
-- ======================================================================
-- Configurable retry policies per service/stage

CREATE TABLE IF NOT EXISTS krai_system.retry_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

COMMENT ON TABLE krai_system.retry_policies IS 'Configurable retry policies per service/stage';
COMMENT ON COLUMN krai_system.retry_policies.exponential_base IS 'Base for exponential backoff calculation';
COMMENT ON COLUMN krai_system.retry_policies.jitter_enabled IS 'Add random jitter to prevent thundering herd';
COMMENT ON COLUMN krai_system.retry_policies.circuit_breaker_threshold IS 'Consecutive failures before circuit opens';

-- Indexes for retry_policies
CREATE INDEX IF NOT EXISTS idx_retry_policies_service
    ON krai_system.retry_policies(service_name);

CREATE INDEX IF NOT EXISTS idx_retry_policies_service_stage
    ON krai_system.retry_policies(service_name, stage_name);

-- ======================================================================
-- Table 6: performance_baselines
-- ======================================================================
-- Stores performance baselines and measurements

CREATE TABLE IF NOT EXISTS krai_system.performance_baselines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_name VARCHAR(50) NOT NULL,
    baseline_avg_seconds NUMERIC(10,3) NOT NULL,
    baseline_p50_seconds NUMERIC(10,3) NOT NULL,
    baseline_p95_seconds NUMERIC(10,3) NOT NULL,
    baseline_p99_seconds NUMERIC(10,3) NOT NULL,
    current_avg_seconds NUMERIC(10,3),
    current_p50_seconds NUMERIC(10,3),
    current_p95_seconds NUMERIC(10,3),
    current_p99_seconds NUMERIC(10,3),
    improvement_percentage NUMERIC(5,2),
    test_document_ids UUID[],
    measurement_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE krai_system.performance_baselines IS 'Stores performance baselines and measurements';
COMMENT ON COLUMN krai_system.performance_baselines.baseline_avg_seconds IS 'Baseline average processing time';
COMMENT ON COLUMN krai_system.performance_baselines.improvement_percentage IS 'Percentage improvement from baseline';
COMMENT ON COLUMN krai_system.performance_baselines.test_document_ids IS 'Array of document IDs used for measurement';

-- Indexes for performance_baselines
CREATE INDEX IF NOT EXISTS idx_performance_baselines_stage
    ON krai_system.performance_baselines(stage_name);

CREATE INDEX IF NOT EXISTS idx_performance_baselines_measurement_date
    ON krai_system.performance_baselines(measurement_date DESC);

-- Unique constraint for baseline upsert operations
-- Allows ON CONFLICT (stage_name, measurement_date) in store_baseline()
CREATE UNIQUE INDEX IF NOT EXISTS idx_performance_baselines_stage_date_unique
    ON krai_system.performance_baselines(stage_name, DATE(measurement_date));

-- ======================================================================
-- Seed Data: Default Retry Policies
-- ======================================================================

INSERT INTO krai_system.retry_policies (policy_name, service_name, max_retries, base_delay_seconds)
VALUES
    ('firecrawl_default', 'firecrawl', 3, 1.0),
    ('database_default', 'database', 5, 0.5),
    ('ollama_default', 'ollama', 3, 2.0),
    ('minio_default', 'minio', 3, 1.0)
ON CONFLICT (policy_name) DO NOTHING;

-- ======================================================================
-- Migration Tracking
-- ======================================================================

INSERT INTO krai_system.migrations (migration_name, description)
VALUES (
    '008_pipeline_resilience_schema',
    'Added 6 tables for pipeline resilience: stage_completion_markers, pipeline_errors, alert_queue, alert_configurations, retry_policies, performance_baselines'
)
ON CONFLICT (migration_name) DO NOTHING;

-- ======================================================================
-- ROLLBACK SCRIPT
-- ======================================================================
-- Execute these statements manually only when an explicit rollback is required:
--
-- DROP TABLE IF EXISTS krai_system.performance_baselines CASCADE;
-- DROP TABLE IF EXISTS krai_system.retry_policies CASCADE;
-- DROP TABLE IF EXISTS krai_system.alert_configurations CASCADE;
-- DROP TABLE IF EXISTS krai_system.alert_queue CASCADE;
-- DROP TABLE IF EXISTS krai_system.pipeline_errors CASCADE;
-- DROP TABLE IF EXISTS krai_system.stage_completion_markers CASCADE;
--
-- DELETE FROM krai_system.migrations WHERE migration_name = '008_pipeline_resilience_schema';
