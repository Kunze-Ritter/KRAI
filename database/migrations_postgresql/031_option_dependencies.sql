-- Migration 031: Create option_dependencies table for managing product compatibility

BEGIN;

-- Create enum type for dependency types
CREATE TYPE dependency_type_enum AS ENUM ('requires', 'excludes', 'alternative');

-- Create option_dependencies table
CREATE TABLE IF NOT EXISTS krai_core.option_dependencies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    option_id UUID NOT NULL REFERENCES krai_core.products(id) ON DELETE CASCADE,
    depends_on_option_id UUID NOT NULL REFERENCES krai_core.products(id) ON DELETE CASCADE,
    dependency_type dependency_type_enum NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    UNIQUE(option_id, depends_on_option_id, dependency_type),
    CHECK (option_id != depends_on_option_id)
);

-- Create indexes for faster queries
CREATE INDEX idx_option_dependencies_option_id ON krai_core.option_dependencies(option_id);
CREATE INDEX idx_option_dependencies_depends_on ON krai_core.option_dependencies(depends_on_option_id);
CREATE INDEX idx_option_dependencies_type ON krai_core.option_dependencies(dependency_type);

COMMIT;
