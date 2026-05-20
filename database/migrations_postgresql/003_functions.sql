-- ======================================================================
-- KRAI PostgreSQL Database - Functions & Triggers
-- ======================================================================
-- Version: 1.0 (PostgreSQL-only, consolidated)
-- Created: 2025-12-20
-- Description: RPC functions, triggers, and stage tracking
--              Consolidates: migration 10 (stage tracking) and related functions
-- ======================================================================

-- ======================================================================
-- STAGE TRACKING FUNCTIONS
-- ======================================================================

-- Function: Start a processing stage
CREATE OR REPLACE FUNCTION krai_core.start_stage(
    p_document_id UUID,
    p_stage_name TEXT
) RETURNS VOID AS $$
BEGIN
    UPDATE krai_core.documents
    SET
        stage_status = jsonb_set(
            jsonb_set(
                stage_status,
                ARRAY[p_stage_name, 'status'],
                '"processing"'
            ),
            ARRAY[p_stage_name, 'started_at'],
            to_jsonb(NOW()::TEXT)
        ),
        updated_at = NOW()
    WHERE id = p_document_id;
END;
$$ LANGUAGE plpgsql;

-- Function: Update stage progress
CREATE OR REPLACE FUNCTION krai_core.update_stage_progress(
    p_document_id UUID,
    p_stage_name TEXT,
    p_progress NUMERIC,
    p_metadata JSONB DEFAULT '{}'
) RETURNS VOID AS $$
BEGIN
    UPDATE krai_core.documents
    SET
        stage_status = jsonb_set(
            jsonb_set(
                stage_status,
                ARRAY[p_stage_name, 'progress'],
                to_jsonb(p_progress)
            ),
            ARRAY[p_stage_name, 'metadata'],
            p_metadata
        ),
        updated_at = NOW()
    WHERE id = p_document_id;
END;
$$ LANGUAGE plpgsql;

-- Function: Complete a processing stage
CREATE OR REPLACE FUNCTION krai_core.complete_stage(
    p_document_id UUID,
    p_stage_name TEXT,
    p_metadata JSONB DEFAULT '{}'
) RETURNS VOID AS $$
BEGIN
    UPDATE krai_core.documents
    SET
        stage_status = jsonb_set(
            jsonb_set(
                jsonb_set(
                    jsonb_set(
                        stage_status,
                        ARRAY[p_stage_name, 'status'],
                        '"completed"'
                    ),
                    ARRAY[p_stage_name, 'completed_at'],
                    to_jsonb(NOW()::TEXT)
                ),
                ARRAY[p_stage_name, 'progress'],
                '100'
            ),
            ARRAY[p_stage_name, 'metadata'],
            p_metadata
        ),
        updated_at = NOW()
    WHERE id = p_document_id;
END;
$$ LANGUAGE plpgsql;

-- Function: Mark stage as failed
CREATE OR REPLACE FUNCTION krai_core.fail_stage(
    p_document_id UUID,
    p_stage_name TEXT,
    p_error TEXT,
    p_metadata JSONB DEFAULT '{}'
) RETURNS VOID AS $$
BEGIN
    UPDATE krai_core.documents
    SET
        stage_status = jsonb_set(
            jsonb_set(
                jsonb_set(
                    stage_status,
                    ARRAY[p_stage_name, 'status'],
                    '"failed"'
                ),
                ARRAY[p_stage_name, 'error'],
                to_jsonb(p_error)
            ),
            ARRAY[p_stage_name, 'metadata'],
            p_metadata
        ),
        updated_at = NOW(),
        error_message = p_error
    WHERE id = p_document_id;
END;
$$ LANGUAGE plpgsql;

-- Function: Skip a processing stage
CREATE OR REPLACE FUNCTION krai_core.skip_stage(
    p_document_id UUID,
    p_stage_name TEXT,
    p_reason TEXT
) RETURNS VOID AS $$
BEGIN
    UPDATE krai_core.documents
    SET
        stage_status = jsonb_set(
            jsonb_set(
                stage_status,
                ARRAY[p_stage_name, 'status'],
                '"skipped"'
            ),
            ARRAY[p_stage_name, 'metadata'],
            jsonb_build_object('skip_reason', p_reason)
        ),
        updated_at = NOW()
    WHERE id = p_document_id;
END;
$$ LANGUAGE plpgsql;

-- ======================================================================
-- VECTOR SEARCH FUNCTIONS
-- ======================================================================

-- Function: Match chunks by embedding similarity
CREATE OR REPLACE FUNCTION krai_intelligence.match_chunks(
    query_embedding vector(768),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 10
) RETURNS TABLE (
    id uuid,
    document_id uuid,
    chunk_text text,
    page_number int,
    similarity float
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.document_id,
        c.chunk_text,
        c.page_number,
        1 - (c.embedding <=> query_embedding) as similarity
    FROM krai_intelligence.chunks c
    WHERE c.embedding IS NOT NULL
        AND 1 - (c.embedding <=> query_embedding) > match_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- Function: Match images by context embedding
CREATE OR REPLACE FUNCTION krai_intelligence.match_images_by_context(
    query_embedding vector(768),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 10
) RETURNS TABLE (
    id uuid,
    document_id uuid,
    storage_url text,
    ai_description text,
    page_number int,
    similarity float
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        i.id,
        i.document_id,
        i.storage_url,
        i.ai_description,
        i.page_number,
        1 - (i.context_embedding <=> query_embedding) as similarity
    FROM krai_content.images i
    WHERE i.context_embedding IS NOT NULL
        AND 1 - (i.context_embedding <=> query_embedding) > match_threshold
    ORDER BY i.context_embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- Function: Multimodal search (chunks, images, videos, links, tables)
CREATE OR REPLACE FUNCTION krai_intelligence.match_multimodal(
    query_embedding vector(768),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 10
) RETURNS TABLE (
    source_id uuid,
    source_type text,
    content text,
    document_id uuid,
    page_number int,
    similarity float
) AS $$
BEGIN
    RETURN QUERY
    WITH all_matches AS (
        -- Text chunks
        SELECT
            c.id as source_id,
            'chunk'::text as source_type,
            c.chunk_text as content,
            c.document_id,
            c.page_number,
            1 - (c.embedding <=> query_embedding) as similarity
        FROM krai_intelligence.chunks c
        WHERE c.embedding IS NOT NULL
            AND 1 - (c.embedding <=> query_embedding) > match_threshold

        UNION ALL

        -- Images
        SELECT
            i.id as source_id,
            'image'::text as source_type,
            COALESCE(i.ai_description, i.figure_context, '') as content,
            i.document_id,
            i.page_number,
            1 - (i.context_embedding <=> query_embedding) as similarity
        FROM krai_content.images i
        WHERE i.context_embedding IS NOT NULL
            AND 1 - (i.context_embedding <=> query_embedding) > match_threshold

        UNION ALL

        -- Videos
        SELECT
            v.id as source_id,
            'video'::text as source_type,
            COALESCE(v.description, v.title, '') as content,
            v.document_id,
            v.page_number,
            1 - (v.context_embedding <=> query_embedding) as similarity
        FROM krai_content.videos v
        WHERE v.context_embedding IS NOT NULL
            AND 1 - (v.context_embedding <=> query_embedding) > match_threshold

        UNION ALL

        -- Links
        SELECT
            l.id as source_id,
            'link'::text as source_type,
            COALESCE(l.description, l.url, '') as content,
            l.document_id,
            l.page_number,
            1 - (l.context_embedding <=> query_embedding) as similarity
        FROM krai_content.links l
        WHERE l.context_embedding IS NOT NULL
            AND 1 - (l.context_embedding <=> query_embedding) > match_threshold

        UNION ALL

        -- Structured tables
        SELECT
            t.id as source_id,
            'table'::text as source_type,
            COALESCE(t.table_markdown, '') as content,
            t.document_id,
            t.page_number,
            1 - (t.table_embedding <=> query_embedding) as similarity
        FROM krai_intelligence.structured_tables t
        WHERE t.table_embedding IS NOT NULL
            AND 1 - (t.table_embedding <=> query_embedding) > match_threshold
    )
    SELECT * FROM all_matches
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- ======================================================================
-- UTILITY FUNCTIONS
-- ======================================================================

-- Function: Get embedding statistics
CREATE OR REPLACE FUNCTION krai_intelligence.get_embedding_stats()
RETURNS TABLE (
    total_chunks bigint,
    chunks_with_embeddings bigint,
    embedding_coverage_percent numeric
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::bigint as total_chunks,
        COUNT(embedding)::bigint as chunks_with_embeddings,
        ROUND((COUNT(embedding)::numeric / NULLIF(COUNT(*), 0)) * 100, 2) as embedding_coverage_percent
    FROM krai_intelligence.chunks;
END;
$$ LANGUAGE plpgsql;

-- ======================================================================
-- TRIGGERS
-- ======================================================================

-- Trigger: Update updated_at timestamp on row modification
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to all relevant tables
DROP TRIGGER IF EXISTS update_manufacturers_updated_at ON krai_core.manufacturers;
CREATE TRIGGER update_manufacturers_updated_at
    BEFORE UPDATE ON krai_core.manufacturers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_products_updated_at ON krai_core.products;
CREATE TRIGGER update_products_updated_at
    BEFORE UPDATE ON krai_core.products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_documents_updated_at ON krai_core.documents;
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON krai_core.documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_chunks_updated_at ON krai_intelligence.chunks;
CREATE TRIGGER update_chunks_updated_at
    BEFORE UPDATE ON krai_intelligence.chunks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_images_updated_at ON krai_content.images;
CREATE TRIGGER update_images_updated_at
    BEFORE UPDATE ON krai_content.images
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_videos_updated_at ON krai_content.videos;
CREATE TRIGGER update_videos_updated_at
    BEFORE UPDATE ON krai_content.videos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_links_updated_at ON krai_content.links;
CREATE TRIGGER update_links_updated_at
    BEFORE UPDATE ON krai_content.links
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ======================================================================
-- RECORD MIGRATION
-- ======================================================================

INSERT INTO krai_system.migrations (migration_name, applied_at, description)
VALUES ('003_functions', NOW(), 'PostgreSQL functions and triggers - stage tracking, vector search, utilities')
ON CONFLICT (migration_name) DO NOTHING;

-- ======================================================================
-- VERIFICATION
-- ======================================================================

DO $$
DECLARE
    function_count INTEGER;
    trigger_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO function_count
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname LIKE 'krai_%';

    SELECT COUNT(*) INTO trigger_count
    FROM pg_trigger t
    JOIN pg_class c ON t.tgrelid = c.oid
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE n.nspname LIKE 'krai_%';

    RAISE NOTICE '✅ KRAI PostgreSQL Functions & Triggers Setup Complete';
    RAISE NOTICE '   Functions: %', function_count;
    RAISE NOTICE '   Triggers: %', trigger_count;
    RAISE NOTICE '   Key functions: start_stage, complete_stage, match_chunks, match_multimodal';
END $$;
