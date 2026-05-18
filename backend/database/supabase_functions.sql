-- KRAI Chat Agent - Supabase Functions
-- Diese Funktionen müssen in deiner Supabase Datenbank ausgeführt werden

-- =============================================================================
-- VECTOR SEARCH FUNCTION
-- =============================================================================
CREATE OR REPLACE FUNCTION search_documents(
  query_text TEXT,
  limit_count INTEGER DEFAULT 5
)
RETURNS TABLE (
  id UUID,
  filename TEXT,
  content TEXT,
  similarity_score FLOAT,
  page_number INTEGER,
  chunk_index INTEGER
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    c.id,
    d.filename,
    c.content,
    (c.embedding <=> (
      SELECT embedding
      FROM krai_intelligence.embeddings e
      WHERE e.chunk_id = c.id
      LIMIT 1
    )) as similarity_score,
    c.page_number,
    c.chunk_index
  FROM krai_content.chunks c
  JOIN krai_core.documents d ON c.document_id = d.id
  WHERE c.embedding IS NOT NULL
  ORDER BY similarity_score
  LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- MODEL SEARCH FUNCTION
-- =============================================================================
CREATE OR REPLACE FUNCTION search_models(
  search_term TEXT,
  limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
  id UUID,
  name TEXT,
  model TEXT,
  manufacturer_name TEXT,
  product_series_name TEXT,
  created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    p.id,
    p.name,
    p.model,
    m.name as manufacturer_name,
    ps.name as product_series_name,
    p.created_at
  FROM krai_core.products p
  JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
  LEFT JOIN krai_core.product_series ps ON p.product_series_id = ps.id
  WHERE
    p.model ILIKE '%' || search_term || '%' OR
    p.name ILIKE '%' || search_term || '%' OR
    m.name ILIKE '%' || search_term || '%'
  ORDER BY p.created_at DESC
  LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- ERROR CODE SEARCH FUNCTION
-- =============================================================================
CREATE OR REPLACE FUNCTION search_error_codes(
  search_term TEXT,
  limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
  id UUID,
  error_code TEXT,
  description TEXT,
  manufacturer_name TEXT,
  product_model TEXT,
  solution TEXT,
  created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    ec.id,
    ec.error_code,
    ec.description,
    m.name as manufacturer_name,
    p.model as product_model,
    ec.solution,
    ec.created_at
  FROM krai_intelligence.error_codes ec
  JOIN krai_core.manufacturers m ON ec.manufacturer_id = m.id
  LEFT JOIN krai_core.products p ON ec.product_id = p.id
  WHERE
    ec.error_code ILIKE '%' || search_term || '%' OR
    ec.description ILIKE '%' || search_term || '%' OR
    ec.solution ILIKE '%' || search_term || '%'
  ORDER BY ec.created_at DESC
  LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SYSTEM STATUS FUNCTION
-- =============================================================================
CREATE OR REPLACE FUNCTION get_system_status()
RETURNS TABLE (
  total_documents INTEGER,
  completed_documents INTEGER,
  pending_documents INTEGER,
  failed_documents INTEGER,
  total_chunks INTEGER,
  total_images INTEGER,
  total_embeddings INTEGER,
  total_products INTEGER,
  total_manufacturers INTEGER,
  last_processing_time TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    (SELECT COUNT(*)::INTEGER FROM krai_core.documents) as total_documents,
    (SELECT COUNT(*)::INTEGER FROM krai_core.documents WHERE processing_status = 'completed') as completed_documents,
    (SELECT COUNT(*)::INTEGER FROM krai_core.documents WHERE processing_status = 'pending') as pending_documents,
    (SELECT COUNT(*)::INTEGER FROM krai_core.documents WHERE processing_status = 'failed') as failed_documents,
    (SELECT COUNT(*)::INTEGER FROM krai_content.chunks) as total_chunks,
    (SELECT COUNT(*)::INTEGER FROM krai_content.images) as total_images,
    (SELECT COUNT(*)::INTEGER FROM krai_intelligence.embeddings) as total_embeddings,
    (SELECT COUNT(*)::INTEGER FROM krai_core.products) as total_products,
    (SELECT COUNT(*)::INTEGER FROM krai_core.manufacturers) as total_manufacturers,
    (SELECT MAX(created_at) FROM krai_core.documents) as last_processing_time;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- RECENT ACTIVITY FUNCTION
-- =============================================================================
CREATE OR REPLACE FUNCTION get_recent_activity(
  limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
  id UUID,
  activity_type TEXT,
  description TEXT,
  timestamp TIMESTAMP WITH TIME ZONE,
  status TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    al.id,
    al.event_type as activity_type,
    al.description,
    al.created_at as timestamp,
    al.status
  FROM krai_system.audit_log al
  ORDER BY al.created_at DESC
  LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- MANUFACTURER STATS FUNCTION
-- =============================================================================
CREATE OR REPLACE FUNCTION get_manufacturer_stats()
RETURNS TABLE (
  manufacturer_name TEXT,
  document_count INTEGER,
  product_count INTEGER,
  model_count INTEGER
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    m.name as manufacturer_name,
    COUNT(DISTINCT d.id)::INTEGER as document_count,
    COUNT(DISTINCT p.id)::INTEGER as product_count,
    COUNT(DISTINCT p.model)::INTEGER as model_count
  FROM krai_core.manufacturers m
  LEFT JOIN krai_core.products p ON m.id = p.manufacturer_id
  LEFT JOIN krai_core.documents d ON d.manufacturer_id = m.id
  GROUP BY m.id, m.name
  ORDER BY document_count DESC;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- GRANT PERMISSIONS
-- =============================================================================
-- Grant execute permissions to authenticated users
GRANT EXECUTE ON FUNCTION search_documents(TEXT, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION search_models(TEXT, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION search_error_codes(TEXT, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION get_system_status() TO authenticated;
GRANT EXECUTE ON FUNCTION get_recent_activity(INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION get_manufacturer_stats() TO authenticated;

-- Grant execute permissions to anon users (for public access)
GRANT EXECUTE ON FUNCTION search_documents(TEXT, INTEGER) TO anon;
GRANT EXECUTE ON FUNCTION search_models(TEXT, INTEGER) TO anon;
GRANT EXECUTE ON FUNCTION search_error_codes(TEXT, INTEGER) TO anon;
GRANT EXECUTE ON FUNCTION get_system_status() TO anon;
GRANT EXECUTE ON FUNCTION get_recent_activity(INTEGER) TO anon;
GRANT EXECUTE ON FUNCTION get_manufacturer_stats() TO anon;

-- =============================================================================
-- CREATE INDEXES FOR PERFORMANCE
-- =============================================================================

-- Vector similarity search index
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON krai_content.chunks USING ivfflat (embedding vector_cosine_ops);

-- Text search indexes
CREATE INDEX IF NOT EXISTS idx_products_model ON krai_core.products USING gin (model gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_products_name ON krai_core.products USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_manufacturers_name ON krai_core.manufacturers USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_error_codes_code ON krai_intelligence.error_codes USING gin (error_code gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_error_codes_description ON krai_intelligence.error_codes USING gin (description gin_trgm_ops);

-- Status and timestamp indexes
CREATE INDEX IF NOT EXISTS idx_documents_status ON krai_core.documents (processing_status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON krai_core.documents (created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON krai_system.audit_log (created_at);

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Test the functions
-- SELECT * FROM search_documents('Fehler Code 13', 5);
-- SELECT * FROM search_models('HP LaserJet', 5);
-- SELECT * FROM search_error_codes('Code 13', 5);
-- SELECT * FROM get_system_status();
-- SELECT * FROM get_recent_activity(5);
-- SELECT * FROM get_manufacturer_stats();
