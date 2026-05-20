-- Migration 032: Create product_configurations table for storing saved configurations

BEGIN;

CREATE TABLE IF NOT EXISTS krai_core.product_configurations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    base_product_id UUID NOT NULL REFERENCES krai_core.products(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    accessory_ids UUID[] DEFAULT '{}',
    validation_status VARCHAR(50) DEFAULT 'valid',
    validation_errors TEXT[],
    validation_warnings TEXT[],
    validation_recommendations TEXT[],
    metadata JSONB,
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT unique_config_per_product_and_name UNIQUE (base_product_id, name)
);

-- Create indexes for faster queries
CREATE INDEX idx_product_configurations_base_product_id
    ON krai_core.product_configurations(base_product_id);
CREATE INDEX idx_product_configurations_created_at
    ON krai_core.product_configurations(created_at DESC);
CREATE INDEX idx_product_configurations_validation_status
    ON krai_core.product_configurations(validation_status);

COMMIT;
