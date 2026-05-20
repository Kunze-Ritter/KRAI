-- Optional: Create stage_metrics table for real-time metrics
-- This is separate from performance_baselines which stores aggregated benchmarks

CREATE TABLE IF NOT EXISTS krai_system.stage_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL,
    stage_name VARCHAR(50) NOT NULL,
    processing_time NUMERIC(10,3) NOT NULL,
    success BOOLEAN NOT NULL DEFAULT TRUE,
    error_message TEXT,
    correlation_id VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_stage_metrics_document
        FOREIGN KEY (document_id)
        REFERENCES krai_core.documents(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_stage_metrics_document
    ON krai_system.stage_metrics(document_id);

CREATE INDEX IF NOT EXISTS idx_stage_metrics_stage
    ON krai_system.stage_metrics(stage_name);

CREATE INDEX IF NOT EXISTS idx_stage_metrics_created
    ON krai_system.stage_metrics(created_at DESC);

COMMENT ON TABLE krai_system.stage_metrics IS 'Real-time stage processing metrics for each document';
