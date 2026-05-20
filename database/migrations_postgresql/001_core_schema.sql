-- ======================================================================
-- KRAI PostgreSQL Database - Core Schema Setup
-- ======================================================================
-- Version: 1.0 (PostgreSQL-only, consolidated)
-- Created: 2025-12-20
-- Description: Complete database schema setup for KRAI Engine
--              Consolidates: extensions, schemas, core tables, indexes
-- ======================================================================

-- ======================================================================
-- EXTENSIONS
-- ======================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "unaccent";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- ======================================================================
-- SCHEMAS
-- ======================================================================

CREATE SCHEMA IF NOT EXISTS krai_core;
CREATE SCHEMA IF NOT EXISTS krai_intelligence;
CREATE SCHEMA IF NOT EXISTS krai_content;
CREATE SCHEMA IF NOT EXISTS krai_system;
CREATE SCHEMA IF NOT EXISTS krai_parts;
CREATE SCHEMA IF NOT EXISTS krai_users;
CREATE SCHEMA IF NOT EXISTS krai_analytics;

COMMENT ON SCHEMA krai_core IS 'Core business entities: manufacturers, products, documents';
COMMENT ON SCHEMA krai_intelligence IS 'AI/ML intelligence: chunks, embeddings, analytics';
COMMENT ON SCHEMA krai_content IS 'Media content: images, videos, links';
COMMENT ON SCHEMA krai_system IS 'System operations: audit, queue, health monitoring';
COMMENT ON SCHEMA krai_parts IS 'Parts catalog and inventory management';
COMMENT ON SCHEMA krai_users IS 'User management and authentication';
COMMENT ON SCHEMA krai_analytics IS 'Analytics and search tracking';

-- ======================================================================
-- MIGRATION TRACKING
-- ======================================================================

CREATE TABLE IF NOT EXISTS krai_system.migrations (
    migration_name VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    description TEXT
);

-- ======================================================================
-- KRAI_CORE TABLES
-- ======================================================================

-- Manufacturers
CREATE TABLE IF NOT EXISTS krai_core.manufacturers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    short_name VARCHAR(10),
    country VARCHAR(50),
    website VARCHAR(255),
    support_email VARCHAR(255),
    support_phone VARCHAR(50),
    logo_url TEXT,
    is_oem BOOLEAN DEFAULT false,
    oem_manufacturer_id UUID REFERENCES krai_core.manufacturers(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Product Series
CREATE TABLE IF NOT EXISTS krai_core.product_series (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    manufacturer_id UUID NOT NULL REFERENCES krai_core.manufacturers(id) ON DELETE CASCADE,
    series_name VARCHAR(100) NOT NULL,
    series_code VARCHAR(50),
    model_pattern VARCHAR(200),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(manufacturer_id, series_name)
);

-- Products
CREATE TABLE IF NOT EXISTS krai_core.products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    manufacturer_id UUID NOT NULL REFERENCES krai_core.manufacturers(id) ON DELETE CASCADE,
    series_id UUID REFERENCES krai_core.product_series(id) ON DELETE SET NULL,
    model_number VARCHAR(100) NOT NULL,
    model_name VARCHAR(200),
    product_code VARCHAR(100),
    product_type VARCHAR(50) NOT NULL DEFAULT 'printer',
    launch_date DATE,
    end_of_life_date DATE,
    oem_product_id UUID REFERENCES krai_core.products(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(manufacturer_id, model_number)
);

-- Documents
CREATE TABLE IF NOT EXISTS krai_core.documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    manufacturer_id UUID REFERENCES krai_core.manufacturers(id) ON DELETE SET NULL,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255),
    file_size BIGINT,
    file_hash VARCHAR(64) UNIQUE,
    storage_path TEXT,
    storage_url TEXT,
    document_type VARCHAR(100),
    language VARCHAR(10) DEFAULT 'en',
    page_count INTEGER,
    processing_status VARCHAR(50) DEFAULT 'pending',
    stage_status JSONB DEFAULT '{}',
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE
);

-- Document-Product Junction
CREATE TABLE IF NOT EXISTS krai_core.document_products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES krai_core.documents(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES krai_core.products(id) ON DELETE CASCADE,
    relevance_score DECIMAL(3,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(document_id, product_id)
);

-- Product Accessories Junction
CREATE TABLE IF NOT EXISTS krai_core.product_accessories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES krai_core.products(id) ON DELETE CASCADE,
    accessory_id UUID NOT NULL REFERENCES krai_core.products(id) ON DELETE CASCADE,
    accessory_type VARCHAR(50),
    is_required BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(product_id, accessory_id),
    CHECK (product_id != accessory_id)
);

-- ======================================================================
-- KRAI_INTELLIGENCE TABLES
-- ======================================================================

-- Chunks (with embeddings)
CREATE TABLE IF NOT EXISTS krai_intelligence.chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES krai_core.documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    page_number INTEGER,
    page_label VARCHAR(50),
    chunk_type VARCHAR(50) DEFAULT 'text',
    token_count INTEGER,
    embedding vector(768),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

-- Structured Tables
CREATE TABLE IF NOT EXISTS krai_intelligence.structured_tables (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES krai_core.documents(id) ON DELETE CASCADE,
    chunk_id UUID REFERENCES krai_intelligence.chunks(id) ON DELETE SET NULL,
    page_number INTEGER,
    table_index INTEGER,
    table_data JSONB NOT NULL,
    table_markdown TEXT,
    column_headers TEXT[],
    row_count INTEGER,
    column_count INTEGER,
    table_embedding vector(768),
    context_embedding vector(768),
    column_embeddings JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Error Codes
CREATE TABLE IF NOT EXISTS krai_intelligence.error_codes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES krai_core.documents(id) ON DELETE SET NULL,
    chunk_id UUID REFERENCES krai_intelligence.chunks(id) ON DELETE SET NULL,
    error_code VARCHAR(50) NOT NULL,
    error_description TEXT,
    solution TEXT,
    page_number INTEGER,
    severity VARCHAR(20),
    category VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ======================================================================
-- KRAI_CONTENT TABLES
-- ======================================================================

-- Images
CREATE TABLE IF NOT EXISTS krai_content.images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES krai_core.documents(id) ON DELETE CASCADE,
    chunk_id UUID REFERENCES krai_intelligence.chunks(id) ON DELETE SET NULL,
    filename VARCHAR(255),
    original_filename VARCHAR(255),
    storage_path TEXT,
    storage_url TEXT NOT NULL,
    file_size INTEGER,
    file_hash VARCHAR(64),
    image_format VARCHAR(10),
    width_px INTEGER,
    height_px INTEGER,
    page_number INTEGER,
    image_index INTEGER,
    image_type VARCHAR(50),
    ai_description TEXT,
    ai_confidence DECIMAL(5,4),
    contains_text BOOLEAN DEFAULT false,
    ocr_text TEXT,
    figure_number VARCHAR(50),
    figure_context TEXT,
    context_caption TEXT,
    page_header TEXT,
    surrounding_paragraphs TEXT[],
    related_error_codes TEXT[],
    related_products TEXT[],
    related_chunks UUID[],
    context_embedding vector(768),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Videos
CREATE TABLE IF NOT EXISTS krai_content.videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES krai_core.documents(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title VARCHAR(500),
    description TEXT,
    duration_seconds INTEGER,
    thumbnail_url TEXT,
    page_number INTEGER,
    video_type VARCHAR(50),
    context_description TEXT,
    related_products TEXT[],
    related_chunks UUID[],
    context_embedding vector(768),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Links
CREATE TABLE IF NOT EXISTS krai_content.links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES krai_core.documents(id) ON DELETE CASCADE,
    video_id UUID REFERENCES krai_content.videos(id) ON DELETE SET NULL,
    url TEXT NOT NULL,
    link_type VARCHAR(50) DEFAULT 'external',
    page_number INTEGER NOT NULL,
    description TEXT,
    link_category VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    context_description TEXT,
    related_chunks UUID[],
    context_embedding vector(768),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Video-Product Junction
CREATE TABLE IF NOT EXISTS krai_content.video_products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id UUID NOT NULL REFERENCES krai_content.videos(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES krai_core.products(id) ON DELETE CASCADE,
    relevance_score DECIMAL(3,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(video_id, product_id)
);

-- ======================================================================
-- KRAI_PARTS TABLES
-- ======================================================================

-- Parts Catalog
CREATE TABLE IF NOT EXISTS krai_parts.parts_catalog (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID REFERENCES krai_core.products(id) ON DELETE SET NULL,
    part_number VARCHAR(100) NOT NULL,
    part_name VARCHAR(200),
    description TEXT,
    category VARCHAR(100),
    price_usd DECIMAL(10,2),
    stock_status VARCHAR(50),
    image_url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(product_id, part_number)
);

-- ======================================================================
-- KRAI_SYSTEM TABLES
-- ======================================================================

-- Processing Queue
CREATE TABLE IF NOT EXISTS krai_system.processing_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES krai_core.documents(id) ON DELETE CASCADE,
    stage VARCHAR(50) NOT NULL,
    priority INTEGER DEFAULT 5,
    status VARCHAR(50) DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    error_message TEXT,
    payload JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Audit Log
CREATE TABLE IF NOT EXISTS krai_system.audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id UUID,
    changes JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- System Metrics
CREATE TABLE IF NOT EXISTS krai_system.system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,4),
    metric_unit VARCHAR(50),
    tags JSONB DEFAULT '{}',
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ======================================================================
-- KRAI_ANALYTICS TABLES
-- ======================================================================

-- Search Analytics
CREATE TABLE IF NOT EXISTS krai_analytics.search_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    query_text TEXT NOT NULL,
    query_type VARCHAR(50),
    result_count INTEGER,
    top_result_id UUID,
    response_time_ms INTEGER,
    filters JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Agent Memory
CREATE TABLE IF NOT EXISTS krai_analytics.agent_memory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL,
    user_id UUID,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ======================================================================
-- INDEXES - Performance Optimization
-- ======================================================================

-- Core indexes
CREATE INDEX IF NOT EXISTS idx_documents_manufacturer ON krai_core.documents(manufacturer_id);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON krai_core.documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_status ON krai_core.documents(processing_status);
CREATE INDEX IF NOT EXISTS idx_products_manufacturer ON krai_core.products(manufacturer_id);
CREATE INDEX IF NOT EXISTS idx_products_series ON krai_core.products(series_id);
CREATE INDEX IF NOT EXISTS idx_products_type ON krai_core.products(product_type);

-- Intelligence indexes
CREATE INDEX IF NOT EXISTS idx_chunks_document ON krai_intelligence.chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_page ON krai_intelligence.chunks(page_number);
CREATE INDEX IF NOT EXISTS idx_error_codes_document ON krai_intelligence.error_codes(document_id);
CREATE INDEX IF NOT EXISTS idx_error_codes_chunk ON krai_intelligence.error_codes(chunk_id);
CREATE INDEX IF NOT EXISTS idx_error_codes_code ON krai_intelligence.error_codes(error_code);

-- Content indexes
CREATE INDEX IF NOT EXISTS idx_images_document ON krai_content.images(document_id);
CREATE INDEX IF NOT EXISTS idx_images_chunk ON krai_content.images(chunk_id);
CREATE INDEX IF NOT EXISTS idx_images_hash ON krai_content.images(file_hash);
CREATE INDEX IF NOT EXISTS idx_videos_document ON krai_content.videos(document_id);
CREATE INDEX IF NOT EXISTS idx_links_document ON krai_content.links(document_id);
CREATE INDEX IF NOT EXISTS idx_links_video ON krai_content.links(video_id);

-- System indexes
CREATE INDEX IF NOT EXISTS idx_queue_status ON krai_system.processing_queue(status);
CREATE INDEX IF NOT EXISTS idx_queue_document ON krai_system.processing_queue(document_id);
CREATE INDEX IF NOT EXISTS idx_queue_stage ON krai_system.processing_queue(stage);

-- Vector indexes (HNSW for fast similarity search)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON krai_intelligence.chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_images_context_embedding ON krai_content.images
    USING hnsw (context_embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Full-text search indexes
CREATE INDEX IF NOT EXISTS idx_chunks_text_search ON krai_intelligence.chunks
    USING gin(to_tsvector('english', chunk_text));

CREATE INDEX IF NOT EXISTS idx_error_codes_text_search ON krai_intelligence.error_codes
    USING gin(to_tsvector('english', coalesce(error_description, '') || ' ' || coalesce(solution, '')));

-- ======================================================================
-- RECORD MIGRATION
-- ======================================================================

INSERT INTO krai_system.migrations (migration_name, applied_at, description)
VALUES ('001_core_schema', NOW(), 'PostgreSQL core schema setup - extensions, schemas, tables, indexes')
ON CONFLICT (migration_name) DO NOTHING;

-- ======================================================================
-- VERIFICATION
-- ======================================================================

DO $$
DECLARE
    schema_count INTEGER;
    table_count INTEGER;
    index_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO schema_count FROM information_schema.schemata WHERE schema_name LIKE 'krai_%';
    SELECT COUNT(*) INTO table_count FROM information_schema.tables WHERE table_schema LIKE 'krai_%';
    SELECT COUNT(*) INTO index_count FROM pg_indexes WHERE schemaname LIKE 'krai_%';

    RAISE NOTICE '✅ KRAI PostgreSQL Core Schema Setup Complete';
    RAISE NOTICE '   Schemas: %', schema_count;
    RAISE NOTICE '   Tables: %', table_count;
    RAISE NOTICE '   Indexes: %', index_count;
    RAISE NOTICE '   Extensions: uuid-ossp, vector, pg_trgm, unaccent, pg_stat_statements';
END $$;
