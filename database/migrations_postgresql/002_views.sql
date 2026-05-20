-- ======================================================================
-- KRAI PostgreSQL Database - Public Views
-- ======================================================================
-- Version: 1.0 (PostgreSQL-only, consolidated)
-- Created: 2025-12-20
-- Description: All public vw_ views for application access
--              Consolidates: migrations 86, 87, 88 and related view migrations
-- ======================================================================

-- Drop any incorrect views from previous migrations
DROP VIEW IF EXISTS public.vw_embeddings CASCADE;
DROP VIEW IF EXISTS public.vw_chunks CASCADE;
DROP VIEW IF EXISTS public.vw_links CASCADE;
DROP VIEW IF EXISTS public.vw_videos CASCADE;
DROP VIEW IF EXISTS public.vw_documents CASCADE;
DROP VIEW IF EXISTS public.vw_images CASCADE;
DROP VIEW IF EXISTS public.vw_manufacturers CASCADE;
DROP VIEW IF EXISTS public.vw_products CASCADE;
DROP VIEW IF EXISTS public.vw_product_series CASCADE;
DROP VIEW IF EXISTS public.vw_document_products CASCADE;
DROP VIEW IF EXISTS public.vw_video_products CASCADE;
DROP VIEW IF EXISTS public.vw_parts CASCADE;
DROP VIEW IF EXISTS public.vw_error_codes CASCADE;
DROP VIEW IF EXISTS public.vw_processing_queue CASCADE;
DROP VIEW IF EXISTS public.vw_search_analytics CASCADE;
DROP VIEW IF EXISTS public.vw_agent_memory CASCADE;

-- ======================================================================
-- CORE VIEWS (from krai_core schema)
-- ======================================================================

-- vw_documents (CRITICAL - used by SearchIndexingProcessor and application)
CREATE OR REPLACE VIEW public.vw_documents AS
SELECT * FROM krai_core.documents;

-- vw_manufacturers
CREATE OR REPLACE VIEW public.vw_manufacturers AS
SELECT * FROM krai_core.manufacturers;

-- vw_products
CREATE OR REPLACE VIEW public.vw_products AS
SELECT * FROM krai_core.products;

-- vw_product_series
CREATE OR REPLACE VIEW public.vw_product_series AS
SELECT * FROM krai_core.product_series;

-- vw_document_products (junction table)
CREATE OR REPLACE VIEW public.vw_document_products AS
SELECT * FROM krai_core.document_products;

-- ======================================================================
-- INTELLIGENCE VIEWS (from krai_intelligence schema)
-- ======================================================================

-- vw_chunks (CRITICAL - includes embedding column!)
-- This is the main table for text chunks with embeddings
CREATE OR REPLACE VIEW public.vw_chunks AS
SELECT * FROM krai_intelligence.chunks;

-- vw_embeddings (ALIAS for vw_chunks)
-- IMPORTANT: Embeddings are stored IN krai_intelligence.chunks (NOT a separate table!)
-- This view exists for backward compatibility with code expecting vw_embeddings
CREATE OR REPLACE VIEW public.vw_embeddings AS
SELECT * FROM krai_intelligence.chunks;

-- vw_error_codes
CREATE OR REPLACE VIEW public.vw_error_codes AS
SELECT * FROM krai_intelligence.error_codes;

-- ======================================================================
-- CONTENT VIEWS (from krai_content schema)
-- ======================================================================

-- vw_images
CREATE OR REPLACE VIEW public.vw_images AS
SELECT * FROM krai_content.images;

-- vw_videos (used by SearchIndexingProcessor)
CREATE OR REPLACE VIEW public.vw_videos AS
SELECT * FROM krai_content.videos;

-- vw_links (used by SearchIndexingProcessor)
CREATE OR REPLACE VIEW public.vw_links AS
SELECT * FROM krai_content.links;

-- vw_video_products (junction table)
CREATE OR REPLACE VIEW public.vw_video_products AS
SELECT * FROM krai_content.video_products;

-- ======================================================================
-- PARTS VIEWS (from krai_parts schema)
-- ======================================================================

-- vw_parts
CREATE OR REPLACE VIEW public.vw_parts AS
SELECT * FROM krai_parts.parts_catalog;

-- ======================================================================
-- SYSTEM VIEWS (from krai_system schema)
-- ======================================================================

-- vw_processing_queue
CREATE OR REPLACE VIEW public.vw_processing_queue AS
SELECT * FROM krai_system.processing_queue;

-- ======================================================================
-- ANALYTICS VIEWS (from krai_analytics schema)
-- ======================================================================

-- vw_search_analytics
CREATE OR REPLACE VIEW public.vw_search_analytics AS
SELECT * FROM krai_analytics.search_analytics;

-- vw_agent_memory
CREATE OR REPLACE VIEW public.vw_agent_memory AS
SELECT * FROM krai_analytics.agent_memory;

-- ======================================================================
-- GRANT PERMISSIONS
-- ======================================================================

-- Core views
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vw_documents TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vw_manufacturers TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vw_products TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vw_product_series TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vw_document_products TO PUBLIC;

-- Intelligence views
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vw_chunks TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vw_embeddings TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vw_error_codes TO PUBLIC;

-- Content views
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vw_images TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vw_videos TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vw_links TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vw_video_products TO PUBLIC;

-- Parts views
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vw_parts TO PUBLIC;

-- System views
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vw_processing_queue TO PUBLIC;

-- Analytics views
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vw_search_analytics TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.vw_agent_memory TO PUBLIC;

-- ======================================================================
-- RECORD MIGRATION
-- ======================================================================

INSERT INTO krai_system.migrations (migration_name, applied_at, description)
VALUES ('002_views', NOW(), 'PostgreSQL public views - all vw_ views for application access')
ON CONFLICT (migration_name) DO NOTHING;

-- ======================================================================
-- VERIFICATION
-- ======================================================================

DO $$
DECLARE
    view_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO view_count
    FROM pg_views
    WHERE schemaname = 'public' AND viewname LIKE 'vw_%';

    RAISE NOTICE '✅ KRAI PostgreSQL Views Setup Complete';
    RAISE NOTICE '   Public views created: %', view_count;
    RAISE NOTICE '   Key views: vw_documents, vw_chunks, vw_embeddings, vw_links, vw_videos';
    RAISE NOTICE '   Note: vw_embeddings is an alias for vw_chunks (embeddings stored in chunks table)';
END $$;

-- Expected views (should be 16):
-- vw_agent_memory, vw_chunks, vw_document_products, vw_documents, vw_embeddings,
-- vw_error_codes, vw_images, vw_links, vw_manufacturers, vw_parts,
-- vw_processing_queue, vw_product_series, vw_products, vw_search_analytics,
-- vw_video_products, vw_videos
