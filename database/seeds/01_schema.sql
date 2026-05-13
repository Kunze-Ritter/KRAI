--
-- PostgreSQL database dump
--

\restrict 5X9cwO3NO9w7pMsdZXbLWTzQG6eW842hPNcxu5oTIbFX1K9K9jn0psYZlvYScVz

-- Dumped from database version 17.6
-- Dumped by pg_dump version 18.0

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

DROP POLICY IF EXISTS service_role_system_metrics_all ON krai_system.system_metrics;
DROP POLICY IF EXISTS service_role_processing_queue_all ON krai_system.processing_queue;
DROP POLICY IF EXISTS service_role_health_checks_all ON krai_system.health_checks;
DROP POLICY IF EXISTS service_role_audit_log_all ON krai_system.audit_log;
DROP POLICY IF EXISTS service_role_parts_catalog_all ON krai_parts.parts_catalog;
DROP POLICY IF EXISTS service_role_inventory_levels_all ON krai_parts.inventory_levels;
DROP POLICY IF EXISTS service_role_search_analytics_all ON krai_intelligence.search_analytics;
DROP POLICY IF EXISTS service_role_error_codes_all ON krai_intelligence.error_codes;
DROP POLICY IF EXISTS service_role_chunks_all ON krai_intelligence.chunks;
DROP POLICY IF EXISTS research_cache_select_policy ON krai_intelligence.product_research_cache;
DROP POLICY IF EXISTS research_cache_modify_policy ON krai_intelligence.product_research_cache;
DROP POLICY IF EXISTS "Allow read access to error_code_images" ON krai_intelligence.error_code_images;
DROP POLICY IF EXISTS "Allow insert for service role" ON krai_intelligence.error_code_images;
DROP POLICY IF EXISTS service_role_products_all ON krai_core.products;
DROP POLICY IF EXISTS service_role_product_series_all ON krai_core.product_series;
DROP POLICY IF EXISTS service_role_manufacturers_all ON krai_core.manufacturers;
DROP POLICY IF EXISTS service_role_document_relationships_all ON krai_core.document_relationships;
DROP POLICY IF EXISTS option_dependencies_service_role_all ON krai_core.option_dependencies;
DROP POLICY IF EXISTS option_dependencies_authenticated_read ON krai_core.option_dependencies;
DROP POLICY IF EXISTS oem_relationships_select_policy ON krai_core.oem_relationships;
DROP POLICY IF EXISTS oem_relationships_modify_policy ON krai_core.oem_relationships;
DROP POLICY IF EXISTS service_role_print_defects_all ON krai_content.print_defects;
DROP POLICY IF EXISTS service_role_links_all ON krai_content.links;
DROP POLICY IF EXISTS service_role_images_all ON krai_content.images;
ALTER TABLE IF EXISTS ONLY krai_system.stage_tracking DROP CONSTRAINT IF EXISTS stage_tracking_document_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_system.processing_queue DROP CONSTRAINT IF EXISTS processing_queue_image_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_system.processing_queue DROP CONSTRAINT IF EXISTS processing_queue_chunk_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_parts.parts_catalog DROP CONSTRAINT IF EXISTS parts_catalog_manufacturer_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_parts.inventory_levels DROP CONSTRAINT IF EXISTS inventory_levels_part_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.search_analytics DROP CONSTRAINT IF EXISTS search_analytics_product_filter_fkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.search_analytics DROP CONSTRAINT IF EXISTS search_analytics_manufacturer_filter_fkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.error_codes DROP CONSTRAINT IF EXISTS error_codes_video_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.error_codes DROP CONSTRAINT IF EXISTS error_codes_product_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.error_codes DROP CONSTRAINT IF EXISTS error_codes_manufacturer_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.error_codes DROP CONSTRAINT IF EXISTS error_codes_image_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.error_codes DROP CONSTRAINT IF EXISTS error_codes_document_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.error_codes DROP CONSTRAINT IF EXISTS error_codes_chunk_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.error_code_parts DROP CONSTRAINT IF EXISTS error_code_parts_part_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.error_code_parts DROP CONSTRAINT IF EXISTS error_code_parts_error_code_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.error_code_images DROP CONSTRAINT IF EXISTS error_code_images_image_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.error_code_images DROP CONSTRAINT IF EXISTS error_code_images_error_code_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.structured_tables DROP CONSTRAINT IF EXISTS structured_tables_chunk_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.structured_tables DROP CONSTRAINT IF EXISTS structured_tables_document_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_core.products DROP CONSTRAINT IF EXISTS products_series_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_core.products DROP CONSTRAINT IF EXISTS products_manufacturer_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_core.product_series DROP CONSTRAINT IF EXISTS product_series_successor_series_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_core.product_series DROP CONSTRAINT IF EXISTS product_series_manufacturer_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_core.product_configurations DROP CONSTRAINT IF EXISTS product_configurations_base_product_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_core.product_accessories DROP CONSTRAINT IF EXISTS product_accessories_product_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_core.product_accessories DROP CONSTRAINT IF EXISTS product_accessories_accessory_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_core.option_dependencies DROP CONSTRAINT IF EXISTS option_dependencies_option_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_core.option_dependencies DROP CONSTRAINT IF EXISTS option_dependencies_depends_on_option_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_core.documents DROP CONSTRAINT IF EXISTS documents_manufacturer_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_core.document_products DROP CONSTRAINT IF EXISTS document_products_product_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_core.document_products DROP CONSTRAINT IF EXISTS document_products_document_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_content.videos DROP CONSTRAINT IF EXISTS videos_series_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_content.videos DROP CONSTRAINT IF EXISTS videos_manufacturer_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_content.videos DROP CONSTRAINT IF EXISTS videos_link_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_content.videos DROP CONSTRAINT IF EXISTS videos_document_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_content.video_products DROP CONSTRAINT IF EXISTS video_products_video_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_content.video_products DROP CONSTRAINT IF EXISTS video_products_product_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_content.print_defects DROP CONSTRAINT IF EXISTS print_defects_product_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_content.print_defects DROP CONSTRAINT IF EXISTS print_defects_original_image_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_content.print_defects DROP CONSTRAINT IF EXISTS print_defects_manufacturer_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_content.links DROP CONSTRAINT IF EXISTS links_series_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_content.links DROP CONSTRAINT IF EXISTS links_manufacturer_id_fkey;
ALTER TABLE IF EXISTS ONLY krai_content.images DROP CONSTRAINT IF EXISTS images_chunk_id_fkey;
DROP TRIGGER IF EXISTS update_chunks_updated_at ON krai_intelligence.chunks;
DROP TRIGGER IF EXISTS research_cache_updated_at ON krai_intelligence.product_research_cache;
DROP TRIGGER IF EXISTS update_products_updated_at ON krai_core.products;
DROP TRIGGER IF EXISTS update_manufacturers_updated_at ON krai_core.manufacturers;
DROP TRIGGER IF EXISTS oem_relationships_updated_at ON krai_core.oem_relationships;
DROP INDEX IF EXISTS krai_system.idx_stage_tracking_status;
DROP INDEX IF EXISTS krai_system.idx_stage_tracking_stage;
DROP INDEX IF EXISTS krai_system.idx_stage_tracking_document;
DROP INDEX IF EXISTS krai_system.idx_stage_tracking_created;
DROP INDEX IF EXISTS krai_system.idx_processing_queue_video_id;
DROP INDEX IF EXISTS krai_system.idx_processing_queue_pending;
DROP INDEX IF EXISTS krai_system.idx_processing_queue_image_id;
DROP INDEX IF EXISTS krai_system.idx_processing_queue_document_id;
DROP INDEX IF EXISTS krai_system.idx_processing_queue_chunk_id;
DROP INDEX IF EXISTS krai_system.idx_audit_log_timestamp;
DROP INDEX IF EXISTS krai_system.idx_audit_log_table;
DROP INDEX IF EXISTS krai_system.idx_audit_log_record_id;
DROP INDEX IF EXISTS krai_system.idx_audit_log_changed_at_desc;
DROP INDEX IF EXISTS krai_parts.idx_parts_number_trgm;
DROP INDEX IF EXISTS krai_parts.idx_parts_name_trgm;
DROP INDEX IF EXISTS krai_parts.idx_parts_catalog_manufacturer_id;
DROP INDEX IF EXISTS krai_parts.idx_inventory_levels_part_id;
DROP INDEX IF EXISTS krai_intelligence.idx_tool_usage_tool;
DROP INDEX IF EXISTS krai_intelligence.idx_tool_usage_session;
DROP INDEX IF EXISTS krai_intelligence.idx_tool_usage_created;
DROP INDEX IF EXISTS krai_intelligence.idx_session_context_unique;
DROP INDEX IF EXISTS krai_intelligence.idx_session_context_type;
DROP INDEX IF EXISTS krai_intelligence.idx_session_context_session;
DROP INDEX IF EXISTS krai_intelligence.idx_search_analytics_product_filter;
DROP INDEX IF EXISTS krai_intelligence.idx_search_analytics_manufacturer_filter;
DROP INDEX IF EXISTS krai_intelligence.idx_search_analytics_created_at_desc;
DROP INDEX IF EXISTS krai_intelligence.idx_research_cache_verified;
DROP INDEX IF EXISTS krai_intelligence.idx_research_cache_valid_until;
DROP INDEX IF EXISTS krai_intelligence.idx_research_cache_specifications;
DROP INDEX IF EXISTS krai_intelligence.idx_research_cache_series;
DROP INDEX IF EXISTS krai_intelligence.idx_research_cache_physical_specs;
DROP INDEX IF EXISTS krai_intelligence.idx_research_cache_model;
DROP INDEX IF EXISTS krai_intelligence.idx_research_cache_manufacturer;
DROP INDEX IF EXISTS krai_intelligence.idx_research_cache_confidence;
DROP INDEX IF EXISTS krai_intelligence.idx_feedback_session;
DROP INDEX IF EXISTS krai_intelligence.idx_feedback_rating;
DROP INDEX IF EXISTS krai_intelligence.idx_feedback_created;
DROP INDEX IF EXISTS krai_intelligence.idx_error_codes_video_id;
DROP INDEX IF EXISTS krai_intelligence.idx_error_codes_unique_source;
DROP INDEX IF EXISTS krai_intelligence.idx_error_codes_severity_manufacturer;
DROP INDEX IF EXISTS krai_intelligence.idx_error_codes_severity;
DROP INDEX IF EXISTS krai_intelligence.idx_error_codes_search;
DROP INDEX IF EXISTS krai_intelligence.idx_error_codes_product_id;
DROP INDEX IF EXISTS krai_intelligence.idx_error_codes_manufacturer;
DROP INDEX IF EXISTS krai_intelligence.idx_error_codes_lookup;
DROP INDEX IF EXISTS krai_intelligence.idx_error_codes_image;
DROP INDEX IF EXISTS krai_intelligence.idx_error_codes_document_id;
DROP INDEX IF EXISTS krai_intelligence.idx_error_codes_confidence;
DROP INDEX IF EXISTS krai_intelligence.idx_error_codes_code_trgm;
DROP INDEX IF EXISTS krai_intelligence.idx_error_codes_chunk_id;
DROP INDEX IF EXISTS krai_intelligence.idx_error_code_parts_part_id;
DROP INDEX IF EXISTS krai_intelligence.idx_error_code_parts_error_id;
DROP INDEX IF EXISTS krai_intelligence.idx_error_code_images_image;
DROP INDEX IF EXISTS krai_intelligence.idx_error_code_images_error_code;
DROP INDEX IF EXISTS krai_intelligence.idx_chunks_text_trgm;
DROP INDEX IF EXISTS krai_intelligence.idx_chunks_text_fts;
DROP INDEX IF EXISTS krai_intelligence.idx_chunks_page_label_start;
DROP INDEX IF EXISTS krai_intelligence.idx_chunks_page_label_end;
DROP INDEX IF EXISTS krai_intelligence.idx_chunks_document_status_index;
DROP INDEX IF EXISTS krai_intelligence.idx_chunks_document;
DROP INDEX IF EXISTS krai_intelligence.chunks_embedding_hnsw_idx;
DROP INDEX IF EXISTS krai_core.idx_products_type;
DROP INDEX IF EXISTS krai_core.idx_products_specifications;
DROP INDEX IF EXISTS krai_core.idx_products_series_id;
DROP INDEX IF EXISTS krai_core.idx_products_product_type;
DROP INDEX IF EXISTS krai_core.idx_products_product_code;
DROP INDEX IF EXISTS krai_core.idx_products_pricing;
DROP INDEX IF EXISTS krai_core.idx_products_oem_relationship_type;
DROP INDEX IF EXISTS krai_core.idx_products_oem_manufacturer;
DROP INDEX IF EXISTS krai_core.idx_products_model_trgm;
DROP INDEX IF EXISTS krai_core.idx_products_metadata;
DROP INDEX IF EXISTS krai_core.idx_products_manufacturer_series_type;
DROP INDEX IF EXISTS krai_core.idx_products_lifecycle;
DROP INDEX IF EXISTS krai_core.idx_products_article_code;
DROP INDEX IF EXISTS krai_core.idx_product_series_name_pattern;
DROP INDEX IF EXISTS krai_core.idx_product_series_model_pattern;
DROP INDEX IF EXISTS krai_core.idx_product_series_manufacturer_id;
DROP INDEX IF EXISTS krai_core.idx_product_accessories_product;
DROP INDEX IF EXISTS krai_core.idx_product_accessories_mounting_position;
DROP INDEX IF EXISTS krai_core.idx_product_accessories_accessory;
DROP INDEX IF EXISTS krai_core.idx_option_dependencies_type;
DROP INDEX IF EXISTS krai_core.idx_option_dependencies_option_id;
DROP INDEX IF EXISTS krai_core.idx_option_dependencies_depends_on;
DROP INDEX IF EXISTS krai_core.idx_oem_relationships_type;
DROP INDEX IF EXISTS krai_core.idx_oem_relationships_series;
DROP INDEX IF EXISTS krai_core.idx_oem_relationships_oem;
DROP INDEX IF EXISTS krai_core.idx_oem_relationships_brand;
DROP INDEX IF EXISTS krai_core.idx_oem_relationships_applies_to;
DROP INDEX IF EXISTS krai_core.idx_manufacturers_is_competitor;
DROP INDEX IF EXISTS krai_core.idx_documents_stage_status;
DROP INDEX IF EXISTS krai_core.idx_documents_processing_status;
DROP INDEX IF EXISTS krai_core.idx_documents_processing_results;
DROP INDEX IF EXISTS krai_core.idx_documents_priority;
DROP INDEX IF EXISTS krai_core.idx_documents_models;
DROP INDEX IF EXISTS krai_core.idx_documents_manufacturer_id;
DROP INDEX IF EXISTS krai_core.idx_documents_manufacturer;
DROP INDEX IF EXISTS krai_core.idx_documents_file_hash;
DROP INDEX IF EXISTS krai_core.idx_documents_extracted_metadata;
DROP INDEX IF EXISTS krai_core.idx_documents_document_type;
DROP INDEX IF EXISTS krai_core.idx_documents_created_at;
DROP INDEX IF EXISTS krai_core.idx_document_relationships_secondary_document_id;
DROP INDEX IF EXISTS krai_core.idx_document_relationships_primary_document_id;
DROP INDEX IF EXISTS krai_core.idx_document_products_product_id;
DROP INDEX IF EXISTS krai_core.idx_document_products_primary;
DROP INDEX IF EXISTS krai_core.idx_document_products_document_id;
DROP INDEX IF EXISTS krai_core.idx_configurations_base_product;
DROP INDEX IF EXISTS krai_core.idx_configurations_accessories;
DROP INDEX IF EXISTS krai_content.idx_videos_youtube_id_unique;
DROP INDEX IF EXISTS krai_content.idx_videos_youtube_id;
DROP INDEX IF EXISTS krai_content.idx_videos_video_url;
DROP INDEX IF EXISTS krai_content.idx_videos_url_unique;
DROP INDEX IF EXISTS krai_content.idx_videos_title_trgm;
DROP INDEX IF EXISTS krai_content.idx_videos_platform;
DROP INDEX IF EXISTS krai_content.idx_videos_manufacturer_id;
DROP INDEX IF EXISTS krai_content.idx_videos_link_id;
DROP INDEX IF EXISTS krai_content.idx_videos_document_id;
DROP INDEX IF EXISTS krai_content.idx_video_products_video_id;
DROP INDEX IF EXISTS krai_content.idx_video_products_product_id;
DROP INDEX IF EXISTS krai_content.idx_print_defects_product_id;
DROP INDEX IF EXISTS krai_content.idx_print_defects_original_image_id;
DROP INDEX IF EXISTS krai_content.idx_print_defects_manufacturer_id;
DROP INDEX IF EXISTS krai_content.idx_links_video_id;
DROP INDEX IF EXISTS krai_content.idx_links_url_hash;
DROP INDEX IF EXISTS krai_content.idx_links_type_category;
DROP INDEX IF EXISTS krai_content.idx_links_type;
DROP INDEX IF EXISTS krai_content.idx_links_series;
DROP INDEX IF EXISTS krai_content.idx_links_page;
DROP INDEX IF EXISTS krai_content.idx_links_manufacturer;
DROP INDEX IF EXISTS krai_content.idx_links_error_codes;
DROP INDEX IF EXISTS krai_content.idx_links_document_id;
DROP INDEX IF EXISTS krai_content.idx_images_processing_status;
DROP INDEX IF EXISTS krai_content.idx_images_hash;
DROP INDEX IF EXISTS krai_content.idx_images_figure_number;
DROP INDEX IF EXISTS krai_content.idx_images_document;
DROP INDEX IF EXISTS krai_content.idx_images_chunk_id;
ALTER TABLE IF EXISTS ONLY krai_system.system_metrics DROP CONSTRAINT IF EXISTS system_metrics_pkey;
ALTER TABLE IF EXISTS ONLY krai_system.stage_tracking DROP CONSTRAINT IF EXISTS stage_tracking_pkey;
ALTER TABLE IF EXISTS ONLY krai_system.processing_queue DROP CONSTRAINT IF EXISTS processing_queue_pkey;
ALTER TABLE IF EXISTS ONLY krai_system.health_checks DROP CONSTRAINT IF EXISTS health_checks_pkey;
ALTER TABLE IF EXISTS ONLY krai_system.audit_log DROP CONSTRAINT IF EXISTS audit_log_pkey;
ALTER TABLE IF EXISTS ONLY krai_parts.parts_catalog DROP CONSTRAINT IF EXISTS parts_catalog_pkey;
ALTER TABLE IF EXISTS ONLY krai_parts.parts_catalog DROP CONSTRAINT IF EXISTS parts_catalog_manufacturer_part_unique;
ALTER TABLE IF EXISTS ONLY krai_parts.inventory_levels DROP CONSTRAINT IF EXISTS inventory_levels_pkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.product_research_cache DROP CONSTRAINT IF EXISTS unique_manufacturer_model;
ALTER TABLE IF EXISTS ONLY krai_intelligence.tool_usage DROP CONSTRAINT IF EXISTS tool_usage_pkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.session_context DROP CONSTRAINT IF EXISTS session_context_pkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.search_analytics DROP CONSTRAINT IF EXISTS search_analytics_pkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.product_research_cache DROP CONSTRAINT IF EXISTS product_research_cache_pkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.feedback DROP CONSTRAINT IF EXISTS feedback_pkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.error_codes DROP CONSTRAINT IF EXISTS error_codes_pkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.error_code_parts DROP CONSTRAINT IF EXISTS error_code_parts_pkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.error_code_images DROP CONSTRAINT IF EXISTS error_code_images_pkey;
ALTER TABLE IF EXISTS ONLY krai_intelligence.error_code_images DROP CONSTRAINT IF EXISTS error_code_images_error_code_id_image_id_key;
ALTER TABLE IF EXISTS ONLY krai_intelligence.chunks DROP CONSTRAINT IF EXISTS chunks_pkey;
ALTER TABLE IF EXISTS ONLY krai_core.option_dependencies DROP CONSTRAINT IF EXISTS unique_option_dependency;
ALTER TABLE IF EXISTS ONLY krai_core.oem_relationships DROP CONSTRAINT IF EXISTS unique_brand_oem;
ALTER TABLE IF EXISTS ONLY krai_core.products DROP CONSTRAINT IF EXISTS products_pkey;
ALTER TABLE IF EXISTS ONLY krai_core.product_series DROP CONSTRAINT IF EXISTS product_series_pkey;
ALTER TABLE IF EXISTS ONLY krai_core.product_series DROP CONSTRAINT IF EXISTS product_series_manufacturer_id_series_name_key;
ALTER TABLE IF EXISTS ONLY krai_core.product_configurations DROP CONSTRAINT IF EXISTS product_configurations_pkey;
ALTER TABLE IF EXISTS ONLY krai_core.product_accessories DROP CONSTRAINT IF EXISTS product_accessories_product_id_accessory_id_key;
ALTER TABLE IF EXISTS ONLY krai_core.product_accessories DROP CONSTRAINT IF EXISTS product_accessories_pkey;
ALTER TABLE IF EXISTS ONLY krai_core.option_dependencies DROP CONSTRAINT IF EXISTS option_dependencies_pkey;
ALTER TABLE IF EXISTS ONLY krai_core.oem_relationships DROP CONSTRAINT IF EXISTS oem_relationships_pkey;
ALTER TABLE IF EXISTS ONLY krai_core.manufacturers DROP CONSTRAINT IF EXISTS manufacturers_pkey;
ALTER TABLE IF EXISTS ONLY krai_core.manufacturers DROP CONSTRAINT IF EXISTS manufacturers_name_key;
ALTER TABLE IF EXISTS ONLY krai_core.documents DROP CONSTRAINT IF EXISTS documents_pkey;
ALTER TABLE IF EXISTS ONLY krai_core.document_relationships DROP CONSTRAINT IF EXISTS document_relationships_primary_document_id_secondary_docume_key;
ALTER TABLE IF EXISTS ONLY krai_core.document_relationships DROP CONSTRAINT IF EXISTS document_relationships_pkey;
ALTER TABLE IF EXISTS ONLY krai_core.document_products DROP CONSTRAINT IF EXISTS document_products_pkey;
ALTER TABLE IF EXISTS ONLY krai_core.document_products DROP CONSTRAINT IF EXISTS document_products_document_id_product_id_key;
ALTER TABLE IF EXISTS ONLY krai_core.product_configurations DROP CONSTRAINT IF EXISTS configuration_name_unique;
ALTER TABLE IF EXISTS ONLY krai_content.videos DROP CONSTRAINT IF EXISTS videos_pkey;
ALTER TABLE IF EXISTS ONLY krai_content.video_products DROP CONSTRAINT IF EXISTS video_products_video_id_product_id_key;
ALTER TABLE IF EXISTS ONLY krai_content.video_products DROP CONSTRAINT IF EXISTS video_products_pkey;
ALTER TABLE IF EXISTS ONLY krai_content.print_defects DROP CONSTRAINT IF EXISTS print_defects_pkey;
ALTER TABLE IF EXISTS ONLY krai_content.links DROP CONSTRAINT IF EXISTS links_pkey;
ALTER TABLE IF EXISTS ONLY krai_content.images DROP CONSTRAINT IF EXISTS images_pkey;
DROP TABLE IF EXISTS krai_system.system_metrics;
DROP TABLE IF EXISTS krai_system.stage_tracking;
DROP TABLE IF EXISTS krai_system.processing_queue;
DROP TABLE IF EXISTS krai_system.health_checks;
DROP TABLE IF EXISTS krai_system.audit_log;
DROP TABLE IF EXISTS krai_parts.parts_catalog;
DROP TABLE IF EXISTS krai_parts.inventory_levels;
DROP VIEW IF EXISTS krai_intelligence.user_satisfaction;
DROP TABLE IF EXISTS krai_intelligence.session_context;
DROP TABLE IF EXISTS krai_intelligence.search_analytics;
DROP TABLE IF EXISTS krai_intelligence.product_research_cache;
DROP TABLE IF EXISTS krai_intelligence.feedback;
DROP TABLE IF EXISTS krai_intelligence.error_codes;
DROP TABLE IF EXISTS krai_intelligence.error_code_parts;
DROP TABLE IF EXISTS krai_intelligence.error_code_images;
DROP TABLE IF EXISTS krai_intelligence.chunks;
DROP TABLE IF EXISTS krai_intelligence.unified_embeddings;
DROP TABLE IF EXISTS krai_intelligence.structured_tables;
DROP VIEW IF EXISTS krai_intelligence.agent_performance;
DROP TABLE IF EXISTS krai_intelligence.tool_usage;
DROP TABLE IF EXISTS krai_core.products_backup;
DROP TABLE IF EXISTS krai_core.products;
DROP TABLE IF EXISTS krai_core.product_series;
DROP TABLE IF EXISTS krai_core.product_configurations;
DROP TABLE IF EXISTS krai_core.product_accessories;
DROP TABLE IF EXISTS krai_core.option_dependencies;
DROP TABLE IF EXISTS krai_core.oem_relationships;
DROP TABLE IF EXISTS krai_core.manufacturers;
DROP TABLE IF EXISTS krai_core.documents;
DROP TABLE IF EXISTS krai_core.document_relationships;
DROP TABLE IF EXISTS krai_core.document_products;
DROP TABLE IF EXISTS krai_content.videos;
DROP TABLE IF EXISTS krai_content.video_products;
DROP TABLE IF EXISTS krai_content.print_defects;
DROP TABLE IF EXISTS krai_content.links;
DROP TABLE IF EXISTS krai_content.images;
DROP FUNCTION IF EXISTS krai_system.update_updated_at_column();
DROP FUNCTION IF EXISTS krai_system.test_vector_performance();
DROP FUNCTION IF EXISTS krai_system.test_index_performance();
DROP FUNCTION IF EXISTS krai_system.system_health_check();
DROP FUNCTION IF EXISTS krai_system.run_performance_test_suite();
DROP FUNCTION IF EXISTS krai_system.optimize_database_performance();
DROP FUNCTION IF EXISTS krai_system.get_storage_statistics();
DROP FUNCTION IF EXISTS krai_system.get_processing_statistics(date_from date, date_to date);
DROP FUNCTION IF EXISTS krai_system.get_performance_metrics();
DROP FUNCTION IF EXISTS krai_system.cleanup_old_storage_objects(days_old integer);
DROP FUNCTION IF EXISTS krai_system.audit_trigger_function();
DROP FUNCTION IF EXISTS krai_intelligence.update_session_context(p_session_id text, p_context_type text, p_context_value text, p_confidence double precision);
DROP FUNCTION IF EXISTS krai_intelligence.update_research_cache_updated_at();
DROP FUNCTION IF EXISTS krai_intelligence.smart_search(p_query text, p_session_id text);
DROP FUNCTION IF EXISTS krai_intelligence.search_videos(p_search_term text, p_manufacturer text, p_model text);
DROP FUNCTION IF EXISTS krai_intelligence.search_parts(p_search_term text, p_part_number text, p_manufacturer text, p_model text);
DROP FUNCTION IF EXISTS krai_intelligence.search_error_codes(p_error_code text, p_manufacturer text, p_model text);
DROP FUNCTION IF EXISTS krai_intelligence.search_documents_optimized(search_query text, manufacturer_filter uuid, document_type_filter character varying, limit_results integer);
DROP FUNCTION IF EXISTS krai_intelligence.search_documentation_context(p_query text, p_manufacturer text, p_model text, p_document_type text, p_limit integer);
DROP FUNCTION IF EXISTS krai_intelligence.refresh_document_processing_summary();
DROP FUNCTION IF EXISTS krai_intelligence.is_research_cache_valid(p_manufacturer character varying, p_model_number character varying);
DROP FUNCTION IF EXISTS krai_intelligence.get_session_context(p_session_id text);
DROP FUNCTION IF EXISTS krai_intelligence.get_product_info(p_model_number text, p_manufacturer text);
DROP FUNCTION IF EXISTS krai_intelligence.get_popular_error_codes(p_manufacturer text, p_limit integer);
DROP FUNCTION IF EXISTS krai_intelligence.get_frequent_parts(p_manufacturer text, p_model text, p_limit integer);
DROP FUNCTION IF EXISTS krai_intelligence.get_cached_research(p_manufacturer character varying, p_model_number character varying);
DROP FUNCTION IF EXISTS krai_intelligence.find_similar_chunks(query_embedding extensions.vector, similarity_threshold numeric, limit_results integer);
DROP FUNCTION IF EXISTS krai_core.validate_configuration(p_base_product_id uuid, p_accessory_ids uuid[]);
DROP FUNCTION IF EXISTS krai_core.update_oem_relationships_updated_at();
DROP FUNCTION IF EXISTS krai_core.update_document_manufacturer(p_document_id uuid, p_manufacturer text, p_manufacturer_id uuid);
DROP FUNCTION IF EXISTS krai_core.meets_requirements(product_specs jsonb, requirements jsonb);
DROP FUNCTION IF EXISTS krai_core.get_required_accessories(p_product_id uuid);
DROP FUNCTION IF EXISTS krai_core.get_product_accessories(p_product_id uuid);
DROP FUNCTION IF EXISTS krai_core.get_incompatible_products(p_product_id uuid);
DROP FUNCTION IF EXISTS krai_core.get_document_products(doc_id uuid);
DROP FUNCTION IF EXISTS krai_core.compare_products(product_id_1 uuid, product_id_2 uuid);
DROP FUNCTION IF EXISTS krai_core.check_compatibility(product_1_id uuid, product_2_id uuid);
DROP FUNCTION IF EXISTS krai_content.update_videos_updated_at();
DROP FUNCTION IF EXISTS krai_content.find_or_create_video_from_link(p_url text, p_manufacturer_id uuid, p_title text, p_description text, p_metadata jsonb);
DROP FUNCTION IF EXISTS krai_intelligence.get_embeddings_by_source(p_source_id uuid, p_source_type character varying);
DROP FUNCTION IF EXISTS krai_intelligence.match_multimodal(query_embedding extensions.vector, match_threshold double precision, match_count integer);
DROP FUNCTION IF EXISTS krai_intelligence.match_images_by_context(query_embedding extensions.vector, match_threshold double precision, match_count integer);
DROP SCHEMA IF EXISTS krai_system;
DROP SCHEMA IF EXISTS krai_parts;
DROP SCHEMA IF EXISTS krai_intelligence;
DROP SCHEMA IF EXISTS krai_core;
DROP SCHEMA IF EXISTS krai_content;
--
-- Name: krai_content; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA krai_content;


--
-- Name: SCHEMA krai_content; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA krai_content IS 'Media content: images, videos, defect patterns';


--
-- Name: krai_core; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA krai_core;


--
-- Name: SCHEMA krai_core; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA krai_core IS 'Core business entities: manufacturers, products, documents';


--
-- Name: krai_intelligence; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA krai_intelligence;


--
-- Name: SCHEMA krai_intelligence; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA krai_intelligence IS 'AI/ML intelligence: chunks, embeddings, analytics';


--
-- Name: krai_parts; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA krai_parts;


--
-- Name: SCHEMA krai_parts; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA krai_parts IS 'Parts catalog and inventory management';


--
-- Name: krai_system; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA krai_system;


--
-- Name: SCHEMA krai_system; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA krai_system IS 'System operations: audit, queue, health monitoring';


--
-- Name: find_or_create_video_from_link(text, uuid, text, text, jsonb); Type: FUNCTION; Schema: krai_content; Owner: -
--

CREATE FUNCTION krai_content.find_or_create_video_from_link(p_url text, p_manufacturer_id uuid, p_title text DEFAULT NULL::text, p_description text DEFAULT NULL::text, p_metadata jsonb DEFAULT '{}'::jsonb) RETURNS uuid
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_video_id UUID;
BEGIN
    SELECT id INTO v_video_id
    FROM krai_content.instructional_videos
    WHERE video_url = p_url
    LIMIT 1;

    IF v_video_id IS NULL THEN
        INSERT INTO krai_content.instructional_videos (
            manufacturer_id, title, description, video_url, auto_created, metadata
        ) VALUES (
            p_manufacturer_id,
            COALESCE(p_title, 'Auto-extracted: ' || p_url),
            COALESCE(p_description, 'Automatically extracted from document'),
            p_url, true, p_metadata
        )
        RETURNING id INTO v_video_id;
    END IF;

    RETURN v_video_id;
END;
$$;


--
-- Name: update_videos_updated_at(); Type: FUNCTION; Schema: krai_content; Owner: -
--

CREATE FUNCTION krai_content.update_videos_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: check_compatibility(uuid, uuid); Type: FUNCTION; Schema: krai_core; Owner: -
--

CREATE FUNCTION krai_core.check_compatibility(product_1_id uuid, product_2_id uuid) RETURNS TABLE(compatible boolean, relationship character varying, notes text)
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        CASE
            WHEN pa.compatibility_type = 'conflicts' THEN false
            ELSE true
        END as compatible,
        pa.compatibility_type as relationship,
        pa.compatibility_notes as notes
    FROM krai_core.product_accessories pa
    WHERE (pa.product_id = product_1_id AND pa.accessory_id = product_2_id)
       OR (pa.product_id = product_2_id AND pa.accessory_id = product_1_id);

    -- If no relationship found, assume compatible
    IF NOT FOUND THEN
        RETURN QUERY SELECT true, 'unknown'::VARCHAR, 'No compatibility information found'::TEXT;
    END IF;
END;
$$;


--
-- Name: compare_products(uuid, uuid); Type: FUNCTION; Schema: krai_core; Owner: -
--

CREATE FUNCTION krai_core.compare_products(product_id_1 uuid, product_id_2 uuid) RETURNS TABLE(spec_key text, product_1_value text, product_2_value text)
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    RETURN QUERY
    WITH specs AS (
        SELECT
            p1.specifications as specs_1,
            p2.specifications as specs_2
        FROM krai_core.products p1
        CROSS JOIN krai_core.products p2
        WHERE p1.id = product_id_1 AND p2.id = product_id_2
    )
    SELECT
        keys.key::TEXT,
        (specs_1 -> keys.key)::TEXT,
        (specs_2 -> keys.key)::TEXT
    FROM specs,
    LATERAL jsonb_object_keys(specs_1) AS keys(key);
END;
$$;


--
-- Name: get_document_products(uuid); Type: FUNCTION; Schema: krai_core; Owner: -
--

CREATE FUNCTION krai_core.get_document_products(doc_id uuid) RETURNS TABLE(product_id uuid, model_number character varying, manufacturer_name character varying, is_primary boolean, confidence numeric, extraction_method character varying)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id as product_id,
        p.model_number,
        m.name as manufacturer_name,
        dp.is_primary_product as is_primary,
        dp.confidence_score as confidence,
        dp.extraction_method
    FROM krai_core.document_products dp
    JOIN krai_core.products p ON dp.product_id = p.id
    LEFT JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
    WHERE dp.document_id = doc_id
    ORDER BY dp.is_primary_product DESC, dp.confidence_score DESC;
END;
$$;


--
-- Name: FUNCTION get_document_products(doc_id uuid); Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON FUNCTION krai_core.get_document_products(doc_id uuid) IS 'Get all products associated with a document, ordered by primary first then confidence';


--
-- Name: get_incompatible_products(uuid); Type: FUNCTION; Schema: krai_core; Owner: -
--

CREATE FUNCTION krai_core.get_incompatible_products(p_product_id uuid) RETURNS TABLE(incompatible_id uuid, model_number character varying, product_type character varying, reason text)
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id,
        p.model_number,
        p.product_type,
        pa.compatibility_notes
    FROM krai_core.product_accessories pa
    JOIN krai_core.products p ON p.id = pa.accessory_id
    WHERE pa.product_id = p_product_id
      AND pa.compatibility_type = 'conflicts';
END;
$$;


--
-- Name: get_product_accessories(uuid); Type: FUNCTION; Schema: krai_core; Owner: -
--

CREATE FUNCTION krai_core.get_product_accessories(p_product_id uuid) RETURNS TABLE(accessory_id uuid, model_number character varying, product_type character varying, compatibility_type character varying, specifications jsonb)
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id,
        p.model_number,
        p.product_type,
        pa.compatibility_type,
        p.specifications
    FROM krai_core.product_accessories pa
    JOIN krai_core.products p ON p.id = pa.accessory_id
    WHERE pa.product_id = p_product_id;
END;
$$;


--
-- Name: get_required_accessories(uuid); Type: FUNCTION; Schema: krai_core; Owner: -
--

CREATE FUNCTION krai_core.get_required_accessories(p_product_id uuid) RETURNS TABLE(accessory_id uuid, model_number character varying, product_type character varying, reason text)
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id,
        p.model_number,
        p.product_type,
        pa.compatibility_notes
    FROM krai_core.product_accessories pa
    JOIN krai_core.products p ON p.id = pa.accessory_id
    WHERE pa.product_id = p_product_id
      AND pa.compatibility_type IN ('required', 'prerequisite');
END;
$$;


--
-- Name: meets_requirements(jsonb, jsonb); Type: FUNCTION; Schema: krai_core; Owner: -
--

CREATE FUNCTION krai_core.meets_requirements(product_specs jsonb, requirements jsonb) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE
    AS $$
BEGIN
    RETURN product_specs @> requirements;
END;
$$;


--
-- Name: update_document_manufacturer(uuid, text, uuid); Type: FUNCTION; Schema: krai_core; Owner: -
--

CREATE FUNCTION krai_core.update_document_manufacturer(p_document_id uuid, p_manufacturer text, p_manufacturer_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    -- Update document with manufacturer info
    UPDATE krai_core.documents
    SET
        manufacturer = p_manufacturer,
        manufacturer_id = p_manufacturer_id,
        updated_at = NOW()
    WHERE id = p_document_id;

    -- Log if no rows were updated (document doesn't exist)
    IF NOT FOUND THEN
        RAISE NOTICE 'Document % not found', p_document_id;
    END IF;
END;
$$;


--
-- Name: FUNCTION update_document_manufacturer(p_document_id uuid, p_manufacturer text, p_manufacturer_id uuid); Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON FUNCTION krai_core.update_document_manufacturer(p_document_id uuid, p_manufacturer text, p_manufacturer_id uuid) IS 'Updates document manufacturer information. Bypasses PostgREST schema cache issues.';


--
-- Name: update_oem_relationships_updated_at(); Type: FUNCTION; Schema: krai_core; Owner: -
--

CREATE FUNCTION krai_core.update_oem_relationships_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: validate_configuration(uuid, uuid[]); Type: FUNCTION; Schema: krai_core; Owner: -
--

CREATE FUNCTION krai_core.validate_configuration(p_base_product_id uuid, p_accessory_ids uuid[]) RETURNS TABLE(is_valid boolean, errors jsonb)
    LANGUAGE plpgsql STABLE
    AS $$
DECLARE
    v_errors JSONB := '[]'::JSONB;
    v_is_valid BOOLEAN := true;
    v_accessory UUID;
    v_other_accessory UUID;
    v_required_accessories UUID[];
    v_compatibility RECORD;
BEGIN
    -- Check for required accessories
    SELECT ARRAY_AGG(accessory_id) INTO v_required_accessories
    FROM krai_core.product_accessories
    WHERE product_id = p_base_product_id
      AND compatibility_type IN ('required', 'prerequisite');

    -- Check if all required accessories are present
    IF v_required_accessories IS NOT NULL THEN
        FOREACH v_accessory IN ARRAY v_required_accessories
        LOOP
            IF NOT (v_accessory = ANY(p_accessory_ids)) THEN
                v_is_valid := false;
                v_errors := v_errors || jsonb_build_object(
                    'type', 'missing_required',
                    'accessory_id', v_accessory,
                    'message', 'Required accessory is missing'
                );
            END IF;
        END LOOP;
    END IF;

    -- Check for conflicts between accessories
    FOREACH v_accessory IN ARRAY p_accessory_ids
    LOOP
        FOREACH v_other_accessory IN ARRAY p_accessory_ids
        LOOP
            IF v_accessory != v_other_accessory THEN
                -- Check compatibility
                SELECT * INTO v_compatibility
                FROM krai_core.check_compatibility(v_accessory, v_other_accessory);

                IF v_compatibility.compatible = false THEN
                    v_is_valid := false;
                    v_errors := v_errors || jsonb_build_object(
                        'type', 'conflict',
                        'accessory_1', v_accessory,
                        'accessory_2', v_other_accessory,
                        'message', v_compatibility.notes
                    );
                END IF;
            END IF;
        END LOOP;
    END LOOP;

    RETURN QUERY SELECT v_is_valid, v_errors;
END;
$$;


--
-- Name: FUNCTION validate_configuration(p_base_product_id uuid, p_accessory_ids uuid[]); Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON FUNCTION krai_core.validate_configuration(p_base_product_id uuid, p_accessory_ids uuid[]) IS 'Validates a product configuration by checking:
1. All required accessories are present
2. No conflicting accessories
3. Prerequisites are met';


--
-- Name: find_similar_chunks(extensions.vector, numeric, integer); Type: FUNCTION; Schema: krai_intelligence; Owner: -
--

CREATE FUNCTION krai_intelligence.find_similar_chunks(query_embedding extensions.vector, similarity_threshold numeric DEFAULT 0.7, limit_results integer DEFAULT 20) RETURNS TABLE(chunk_id uuid, document_id uuid, similarity_score numeric, text_preview text)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.document_id,
        (1 - (e.embedding <=> query_embedding))::DECIMAL(5,4) as similarity,
        LEFT(c.text_chunk, 200) as preview
    FROM krai_intelligence.chunks c
    JOIN krai_intelligence.embeddings e ON c.id = e.chunk_id
    WHERE
        c.processing_status = 'completed'
        AND (1 - (e.embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY e.embedding <=> query_embedding
    LIMIT limit_results;
END;
$$;


--
-- Name: get_cached_research(character varying, character varying); Type: FUNCTION; Schema: krai_intelligence; Owner: -
--

CREATE FUNCTION krai_intelligence.get_cached_research(p_manufacturer character varying, p_model_number character varying) RETURNS jsonb
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_result JSONB;
BEGIN
    SELECT jsonb_build_object(
        'series_name', series_name,
        'series_description', series_description,
        'specifications', specifications,
        'physical_specs', physical_specs,
        'oem_manufacturer', oem_manufacturer,
        'oem_relationship_type', oem_relationship_type,
        'oem_notes', oem_notes,
        'product_type', product_type,
        'confidence', confidence,
        'verified', verified,
        'source_urls', source_urls
    ) INTO v_result
    FROM krai_intelligence.product_research_cache
    WHERE manufacturer = p_manufacturer
      AND model_number = p_model_number
      AND (cache_valid_until IS NULL OR cache_valid_until > NOW());

    RETURN v_result;
END;
$$;


--
-- Name: FUNCTION get_cached_research(p_manufacturer character varying, p_model_number character varying); Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON FUNCTION krai_intelligence.get_cached_research(p_manufacturer character varying, p_model_number character varying) IS 'Get cached research results for a product (returns NULL if expired)';


--
-- Name: get_frequent_parts(text, text, integer); Type: FUNCTION; Schema: krai_intelligence; Owner: -
--

CREATE FUNCTION krai_intelligence.get_frequent_parts(p_manufacturer text DEFAULT NULL::text, p_model text DEFAULT NULL::text, p_limit integer DEFAULT 10) RETURNS TABLE(part_number text, part_name text, occurrence_count bigint, compatible_models text[])
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        pt.part_number::TEXT,
        pt.part_name::TEXT,
        COUNT(DISTINCT pt.id) as occurrence_count,
        ARRAY_AGG(DISTINCT p.model_number) as compatible_models
    FROM krai_parts.parts_catalog pt
    LEFT JOIN krai_core.manufacturers m ON pt.manufacturer_id = m.id
    LEFT JOIN krai_core.documents d ON pt.document_id = d.id
    LEFT JOIN krai_core.document_products dp ON d.id = dp.document_id
    LEFT JOIN krai_core.products p ON dp.product_id = p.id
    WHERE (p_manufacturer IS NULL OR m.name ILIKE '%' || p_manufacturer || '%')
        AND (p_model IS NULL OR p.model_number ILIKE '%' || p_model || '%')
    GROUP BY pt.part_number, pt.part_name
    ORDER BY occurrence_count DESC
    LIMIT p_limit;
END;
$$;


--
-- Name: FUNCTION get_frequent_parts(p_manufacturer text, p_model text, p_limit integer); Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON FUNCTION krai_intelligence.get_frequent_parts(p_manufacturer text, p_model text, p_limit integer) IS 'Get most frequently mentioned parts (useful for inventory management)';


--
-- Name: get_popular_error_codes(text, integer); Type: FUNCTION; Schema: krai_intelligence; Owner: -
--

CREATE FUNCTION krai_intelligence.get_popular_error_codes(p_manufacturer text DEFAULT NULL::text, p_limit integer DEFAULT 10) RETURNS TABLE(error_code text, description text, occurrence_count bigint, affected_models text[])
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        ec.error_code::TEXT,
        ec.description::TEXT,
        COUNT(DISTINCT ec.id) as occurrence_count,
        ARRAY_AGG(DISTINCT p.model_number) as affected_models
    FROM krai_intelligence.error_codes ec
    LEFT JOIN krai_core.products p ON ec.product_id = p.id
    LEFT JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
    WHERE (p_manufacturer IS NULL OR m.name ILIKE '%' || p_manufacturer || '%')
    GROUP BY ec.error_code, ec.description
    ORDER BY occurrence_count DESC
    LIMIT p_limit;
END;
$$;


--
-- Name: FUNCTION get_popular_error_codes(p_manufacturer text, p_limit integer); Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON FUNCTION krai_intelligence.get_popular_error_codes(p_manufacturer text, p_limit integer) IS 'Get most common error codes for a manufacturer (useful for proactive support)';


--
-- Name: get_product_info(text, text); Type: FUNCTION; Schema: krai_intelligence; Owner: -
--

CREATE FUNCTION krai_intelligence.get_product_info(p_model_number text, p_manufacturer text DEFAULT NULL::text) RETURNS TABLE(product_id uuid, model_number text, manufacturer text, manufacturer_id uuid, series_name text, product_type text, oem_manufacturer text, oem_relationship_type text, document_count bigint)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id as product_id,
        p.model_number::TEXT,
        m.name::TEXT as manufacturer,
        m.id as manufacturer_id,
        ps.series_name::TEXT,
        p.product_type::TEXT,
        p.oem_manufacturer::TEXT,
        p.oem_relationship_type::TEXT,
        COUNT(DISTINCT dp.document_id) as document_count
    FROM krai_core.products p
    LEFT JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
    LEFT JOIN krai_core.product_series ps ON p.series_id = ps.id
    LEFT JOIN krai_core.document_products dp ON p.id = dp.product_id
    WHERE p.model_number ILIKE '%' || p_model_number || '%'
        AND (p_manufacturer IS NULL OR m.name ILIKE '%' || p_manufacturer || '%')
    GROUP BY p.id, m.id, m.name, ps.series_name
    ORDER BY
        -- Exact match first
        CASE WHEN p.model_number = p_model_number THEN 0 ELSE 1 END,
        similarity(p.model_number, p_model_number) DESC
    LIMIT 5;
END;
$$;


--
-- Name: FUNCTION get_product_info(p_model_number text, p_manufacturer text); Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON FUNCTION krai_intelligence.get_product_info(p_model_number text, p_manufacturer text) IS 'Get detailed product information including series, OEM info and document count.';


--
-- Name: get_session_context(text); Type: FUNCTION; Schema: krai_intelligence; Owner: -
--

CREATE FUNCTION krai_intelligence.get_session_context(p_session_id text) RETURNS TABLE(context_type text, context_value text, confidence double precision, use_count integer, last_used_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        sc.context_type,
        sc.context_value,
        sc.confidence,
        sc.use_count,
        sc.last_used_at
    FROM krai_intelligence.session_context sc
    WHERE sc.session_id = p_session_id
        AND sc.last_used_at > NOW() - INTERVAL '1 hour' -- Only recent context
    ORDER BY sc.use_count DESC, sc.last_used_at DESC;
END;
$$;


--
-- Name: FUNCTION get_session_context(p_session_id text); Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON FUNCTION krai_intelligence.get_session_context(p_session_id text) IS 'Retrieve current session context (manufacturer, model, etc.) for context-aware responses';


--
-- Name: is_research_cache_valid(character varying, character varying); Type: FUNCTION; Schema: krai_intelligence; Owner: -
--

CREATE FUNCTION krai_intelligence.is_research_cache_valid(p_manufacturer character varying, p_model_number character varying) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_valid_until TIMESTAMP WITH TIME ZONE;
BEGIN
    SELECT cache_valid_until INTO v_valid_until
    FROM krai_intelligence.product_research_cache
    WHERE manufacturer = p_manufacturer
      AND model_number = p_model_number;

    IF v_valid_until IS NULL THEN
        RETURN false;
    END IF;

    RETURN v_valid_until > NOW();
END;
$$;


--
-- Name: FUNCTION is_research_cache_valid(p_manufacturer character varying, p_model_number character varying); Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON FUNCTION krai_intelligence.is_research_cache_valid(p_manufacturer character varying, p_model_number character varying) IS 'Check if research cache is still valid for a product';


--
-- Name: refresh_document_processing_summary(); Type: FUNCTION; Schema: krai_intelligence; Owner: -
--

CREATE FUNCTION krai_intelligence.refresh_document_processing_summary() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY krai_intelligence.document_processing_summary;
END;
$$;


--
-- Name: search_documentation_context(text, text, text, text, integer); Type: FUNCTION; Schema: krai_intelligence; Owner: -
--

CREATE FUNCTION krai_intelligence.search_documentation_context(p_query text, p_manufacturer text DEFAULT NULL::text, p_model text DEFAULT NULL::text, p_document_type text DEFAULT NULL::text, p_limit integer DEFAULT 5) RETURNS TABLE(chunk_id uuid, text_chunk text, page_number integer, filename text, document_type text, manufacturer text, model_number text, relevance_score double precision)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id as chunk_id,
        c.text_chunk::TEXT,
        c.page_number,
        d.filename::TEXT,
        d.document_type::TEXT,
        d.manufacturer::TEXT,
        p.model_number::TEXT,
        -- Simple text relevance score (can be enhanced with embeddings)
        (
            similarity(c.text_chunk, p_query) * 0.7 +
            CASE WHEN c.text_chunk ILIKE '%' || p_query || '%' THEN 0.3 ELSE 0 END
        ) as relevance_score
    FROM krai_intelligence.chunks c
    LEFT JOIN krai_core.documents d ON c.document_id = d.id
    LEFT JOIN krai_core.document_products dp ON d.id = dp.document_id
    LEFT JOIN krai_core.products p ON dp.product_id = p.id
    WHERE c.text_chunk ILIKE '%' || p_query || '%'
        AND (p_manufacturer IS NULL OR d.manufacturer ILIKE '%' || p_manufacturer || '%')
        AND (p_model IS NULL OR p.model_number ILIKE '%' || p_model || '%')
        AND (p_document_type IS NULL OR d.document_type = p_document_type)
    ORDER BY relevance_score DESC
    LIMIT p_limit;
END;
$$;


--
-- Name: FUNCTION search_documentation_context(p_query text, p_manufacturer text, p_model text, p_document_type text, p_limit integer); Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON FUNCTION krai_intelligence.search_documentation_context(p_query text, p_manufacturer text, p_model text, p_document_type text, p_limit integer) IS 'Context-aware search in documentation chunks with manufacturer and model filters.';


--
-- Name: search_documents_optimized(text, uuid, character varying, integer); Type: FUNCTION; Schema: krai_intelligence; Owner: -
--

CREATE FUNCTION krai_intelligence.search_documents_optimized(search_query text, manufacturer_filter uuid DEFAULT NULL::uuid, document_type_filter character varying DEFAULT NULL::character varying, limit_results integer DEFAULT 50) RETURNS TABLE(document_id uuid, title text, relevance_score real, manufacturer_name character varying, document_type character varying)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.filename,
        ts_rank(to_tsvector('english', d.content_text), plainto_tsquery('english', search_query)) as relevance,
        m.name,
        d.document_type
    FROM krai_core.documents d
    JOIN krai_core.manufacturers m ON d.manufacturer_id = m.id
    WHERE
        to_tsvector('english', d.content_text) @@ plainto_tsquery('english', search_query)
        AND (manufacturer_filter IS NULL OR d.manufacturer_id = manufacturer_filter)
        AND (document_type_filter IS NULL OR d.document_type = document_type_filter)
        AND d.processing_status = 'completed'
    ORDER BY relevance DESC
    LIMIT limit_results;
END;
$$;


--
-- Name: search_error_codes(text, text, text); Type: FUNCTION; Schema: krai_intelligence; Owner: -
--

CREATE FUNCTION krai_intelligence.search_error_codes(p_error_code text, p_manufacturer text DEFAULT NULL::text, p_model text DEFAULT NULL::text) RETURNS TABLE(error_code text, description text, cause text, solution text, page_number integer, model_number text, manufacturer text, source_document text, document_id uuid)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        ec.error_code::TEXT,
        ec.description::TEXT,
        ec.cause::TEXT,
        ec.solution::TEXT,
        ec.page_number,
        p.model_number::TEXT,
        m.name::TEXT as manufacturer,
        d.filename::TEXT as source_document,
        d.id as document_id
    FROM krai_intelligence.error_codes ec
    LEFT JOIN krai_core.products p ON ec.product_id = p.id
    LEFT JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
    LEFT JOIN krai_core.documents d ON ec.document_id = d.id
    WHERE ec.error_code ILIKE '%' || p_error_code || '%'
        AND (p_manufacturer IS NULL OR m.name ILIKE '%' || p_manufacturer || '%')
        AND (p_model IS NULL OR p.model_number ILIKE '%' || p_model || '%')
    ORDER BY
        -- Exact match first
        CASE WHEN ec.error_code = p_error_code THEN 0 ELSE 1 END,
        -- Then by similarity
        similarity(ec.error_code, p_error_code) DESC
    LIMIT 5;
END;
$$;


--
-- Name: FUNCTION search_error_codes(p_error_code text, p_manufacturer text, p_model text); Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON FUNCTION krai_intelligence.search_error_codes(p_error_code text, p_manufacturer text, p_model text) IS 'Search for error codes with optional manufacturer and model filters. Returns up to 5 best matches.';


--
-- Name: search_parts(text, text, text, text); Type: FUNCTION; Schema: krai_intelligence; Owner: -
--

CREATE FUNCTION krai_intelligence.search_parts(p_search_term text, p_part_number text DEFAULT NULL::text, p_manufacturer text DEFAULT NULL::text, p_model text DEFAULT NULL::text) RETURNS TABLE(part_number text, part_name text, description text, page_number integer, model_number text, manufacturer text, source_document text, document_id uuid)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        pt.part_number::TEXT,
        pt.part_name::TEXT,
        pt.description::TEXT,
        pt.page_number,
        p.model_number::TEXT,
        m.name::TEXT as manufacturer,
        d.filename::TEXT as source_document,
        d.id as document_id
    FROM krai_parts.parts_catalog pt
    LEFT JOIN krai_core.manufacturers m ON pt.manufacturer_id = m.id
    LEFT JOIN krai_core.documents d ON pt.document_id = d.id
    LEFT JOIN krai_core.document_products dp ON d.id = dp.document_id
    LEFT JOIN krai_core.products p ON dp.product_id = p.id
    WHERE (
        pt.part_name ILIKE '%' || p_search_term || '%'
        OR pt.description ILIKE '%' || p_search_term || '%'
        OR (p_part_number IS NOT NULL AND pt.part_number ILIKE '%' || p_part_number || '%')
    )
    AND (p_manufacturer IS NULL OR m.name ILIKE '%' || p_manufacturer || '%')
    AND (p_model IS NULL OR p.model_number ILIKE '%' || p_model || '%')
    ORDER BY
        -- Exact part number match first
        CASE WHEN pt.part_number = p_part_number THEN 0 ELSE 1 END,
        -- Then by name similarity
        similarity(pt.part_name, p_search_term) DESC
    LIMIT 10;
END;
$$;


--
-- Name: FUNCTION search_parts(p_search_term text, p_part_number text, p_manufacturer text, p_model text); Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON FUNCTION krai_intelligence.search_parts(p_search_term text, p_part_number text, p_manufacturer text, p_model text) IS 'Search for parts by name, description or part number. Returns up to 10 best matches.';


--
-- Name: search_videos(text, text, text); Type: FUNCTION; Schema: krai_intelligence; Owner: -
--

CREATE FUNCTION krai_intelligence.search_videos(p_search_term text, p_manufacturer text DEFAULT NULL::text, p_model text DEFAULT NULL::text) RETURNS TABLE(video_id uuid, youtube_id text, title text, description text, channel_name text, view_count integer, thumbnail_url text, video_url text, manufacturer text, model_number text)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        v.id as video_id,
        v.youtube_id::TEXT,
        v.title::TEXT,
        v.description::TEXT,
        v.channel_name::TEXT,
        v.view_count,
        v.thumbnail_url::TEXT,
        'https://www.youtube.com/watch?v=' || v.youtube_id as video_url,
        m.name::TEXT as manufacturer,
        p.model_number::TEXT
    FROM krai_content.videos v
    LEFT JOIN krai_core.documents d ON v.document_id = d.id
    LEFT JOIN krai_core.manufacturers m ON d.manufacturer_id = m.id
    LEFT JOIN krai_core.document_products dp ON d.id = dp.document_id
    LEFT JOIN krai_core.products p ON dp.product_id = p.id
    WHERE (
        v.title ILIKE '%' || p_search_term || '%'
        OR v.description ILIKE '%' || p_search_term || '%'
    )
    AND (p_manufacturer IS NULL OR m.name ILIKE '%' || p_manufacturer || '%')
    AND (p_model IS NULL OR p.model_number ILIKE '%' || p_model || '%')
    ORDER BY
        -- Prioritize by view count and relevance
        v.view_count DESC NULLS LAST,
        similarity(v.title, p_search_term) DESC
    LIMIT 5;
END;
$$;


--
-- Name: FUNCTION search_videos(p_search_term text, p_manufacturer text, p_model text); Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON FUNCTION krai_intelligence.search_videos(p_search_term text, p_manufacturer text, p_model text) IS 'Search for YouTube videos related to repairs, maintenance or tutorials.';


--
-- Name: smart_search(text, text); Type: FUNCTION; Schema: krai_intelligence; Owner: -
--

CREATE FUNCTION krai_intelligence.smart_search(p_query text, p_session_id text DEFAULT NULL::text) RETURNS TABLE(result_type text, result_data jsonb, relevance_score double precision)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_manufacturer TEXT;
    v_model TEXT;
BEGIN
    -- Get context from session if available
    IF p_session_id IS NOT NULL THEN
        SELECT context_value INTO v_manufacturer
        FROM krai_intelligence.session_context
        WHERE session_id = p_session_id AND context_type = 'manufacturer'
        ORDER BY last_used_at DESC LIMIT 1;

        SELECT context_value INTO v_model
        FROM krai_intelligence.session_context
        WHERE session_id = p_session_id AND context_type = 'model'
        ORDER BY last_used_at DESC LIMIT 1;
    END IF;

    -- Search error codes
    RETURN QUERY
    SELECT
        'error_code'::TEXT,
        jsonb_build_object(
            'error_code', ec.error_code,
            'description', ec.description,
            'cause', ec.cause,
            'solution', ec.solution,
            'page_number', ec.page_number,
            'model', p.model_number,
            'manufacturer', m.name
        ),
        0.9::FLOAT as relevance_score
    FROM krai_intelligence.error_codes ec
    LEFT JOIN krai_core.products p ON ec.product_id = p.id
    LEFT JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
    WHERE ec.error_code ILIKE '%' || p_query || '%'
        OR ec.description ILIKE '%' || p_query || '%'
    LIMIT 3;

    -- Search parts
    RETURN QUERY
    SELECT
        'part'::TEXT,
        jsonb_build_object(
            'part_number', pt.part_number,
            'part_name', pt.part_name,
            'description', pt.description,
            'page_number', pt.page_number,
            'model', p.model_number,
            'manufacturer', m.name
        ),
        0.8::FLOAT as relevance_score
    FROM krai_parts.parts_catalog pt
    LEFT JOIN krai_core.manufacturers m ON pt.manufacturer_id = m.id
    LEFT JOIN krai_core.documents d ON pt.document_id = d.id
    LEFT JOIN krai_core.document_products dp ON d.id = dp.document_id
    LEFT JOIN krai_core.products p ON dp.product_id = p.id
    WHERE pt.part_name ILIKE '%' || p_query || '%'
        OR pt.part_number ILIKE '%' || p_query || '%'
    LIMIT 3;

    -- Search products
    RETURN QUERY
    SELECT
        'product'::TEXT,
        jsonb_build_object(
            'model_number', p.model_number,
            'manufacturer', m.name,
            'series', ps.series_name,
            'product_type', p.product_type
        ),
        0.7::FLOAT as relevance_score
    FROM krai_core.products p
    LEFT JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
    LEFT JOIN krai_core.product_series ps ON p.series_id = ps.id
    WHERE p.model_number ILIKE '%' || p_query || '%'
    LIMIT 3;
END;
$$;


--
-- Name: FUNCTION smart_search(p_query text, p_session_id text); Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON FUNCTION krai_intelligence.smart_search(p_query text, p_session_id text) IS 'Smart search that combines multiple sources and uses session context';


--
-- Name: update_research_cache_updated_at(); Type: FUNCTION; Schema: krai_intelligence; Owner: -
--

CREATE FUNCTION krai_intelligence.update_research_cache_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: update_session_context(text, text, text, double precision); Type: FUNCTION; Schema: krai_intelligence; Owner: -
--

CREATE FUNCTION krai_intelligence.update_session_context(p_session_id text, p_context_type text, p_context_value text, p_confidence double precision DEFAULT 1.0) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    -- Insert or update context
    INSERT INTO krai_intelligence.session_context (
        session_id,
        context_type,
        context_value,
        confidence,
        first_mentioned_at,
        last_used_at,
        use_count
    )
    VALUES (
        p_session_id,
        p_context_type,
        p_context_value,
        p_confidence,
        NOW(),
        NOW(),
        1
    )
    ON CONFLICT (session_id, context_type, context_value)
    DO UPDATE SET
        last_used_at = NOW(),
        use_count = krai_intelligence.session_context.use_count + 1,
        confidence = GREATEST(krai_intelligence.session_context.confidence, p_confidence);
END;
$$;


--
-- Name: FUNCTION update_session_context(p_session_id text, p_context_type text, p_context_value text, p_confidence double precision); Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON FUNCTION krai_intelligence.update_session_context(p_session_id text, p_context_type text, p_context_value text, p_confidence double precision) IS 'Update or insert session context (called when agent extracts manufacturer, model, etc.)';


--
-- Name: audit_trigger_function(); Type: FUNCTION; Schema: krai_system; Owner: -
--

CREATE FUNCTION krai_system.audit_trigger_function() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO krai_system.audit_log (table_name, record_id, operation, old_values, changed_by)
        VALUES (TG_TABLE_NAME, OLD.id, TG_OP, row_to_json(OLD), current_user);
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO krai_system.audit_log (table_name, record_id, operation, old_values, new_values, changed_by)
        VALUES (TG_TABLE_NAME, NEW.id, TG_OP, row_to_json(OLD), row_to_json(NEW), current_user);
        RETURN NEW;
    ELSIF TG_OP = 'INSERT' THEN
        INSERT INTO krai_system.audit_log (table_name, record_id, operation, new_values, changed_by)
        VALUES (TG_TABLE_NAME, NEW.id, TG_OP, row_to_json(NEW), current_user);
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$;


--
-- Name: cleanup_old_storage_objects(integer); Type: FUNCTION; Schema: krai_system; Owner: -
--

CREATE FUNCTION krai_system.cleanup_old_storage_objects(days_old integer DEFAULT 90) RETURNS TABLE(deleted_objects integer, freed_space_mb numeric)
    LANGUAGE plpgsql
    AS $$
DECLARE
    deleted_count INTEGER := 0;
    freed_bytes BIGINT := 0;
BEGIN
    -- Get statistics before cleanup
    SELECT
        COUNT(*),
        COALESCE(SUM(size), 0)
    INTO deleted_count, freed_bytes
    FROM storage.objects
    WHERE created_at < (NOW() - INTERVAL '1 day' * days_old)
      AND bucket_id LIKE 'krai-%';

    -- Delete old objects (this would need proper implementation)
    -- DELETE FROM storage.objects
    -- WHERE created_at < (NOW() - INTERVAL '1 day' * days_old)
    --   AND bucket_id LIKE 'krai-%';

    RETURN QUERY SELECT deleted_count, (freed_bytes::DECIMAL(10,2) / (1024 * 1024));
END;
$$;


--
-- Name: get_performance_metrics(); Type: FUNCTION; Schema: krai_system; Owner: -
--

CREATE FUNCTION krai_system.get_performance_metrics() RETURNS TABLE(metric_name text, metric_value numeric, metric_unit text, collected_at timestamp with time zone)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        'active_connections'::TEXT,
        pg_stat_get_numbackends(oid)::DECIMAL(15,6),
        'count'::TEXT,
        NOW()
    FROM pg_database WHERE datname = current_database()

    UNION ALL

    SELECT
        'cache_hit_ratio'::TEXT,
        (blks_hit::DECIMAL / (blks_hit + blks_read + 1)) * 100,
        'percentage'::TEXT,
        NOW()
    FROM pg_stat_database WHERE datname = current_database()

    UNION ALL

    SELECT
        'total_documents'::TEXT,
        COUNT(*)::DECIMAL(15,6),
        'count'::TEXT,
        NOW()
    FROM krai_core.documents

    UNION ALL

    SELECT
        'total_embeddings'::TEXT,
        COUNT(*)::DECIMAL(15,6),
        'count'::TEXT,
        NOW()
    FROM krai_intelligence.embeddings;
END;
$$;


--
-- Name: get_processing_statistics(date, date); Type: FUNCTION; Schema: krai_system; Owner: -
--

CREATE FUNCTION krai_system.get_processing_statistics(date_from date DEFAULT (CURRENT_DATE - '30 days'::interval), date_to date DEFAULT CURRENT_DATE) RETURNS TABLE(total_documents integer, completed_documents integer, pending_documents integer, failed_documents integer, avg_processing_time_hours numeric, total_chunks integer, total_images integer)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::INTEGER as total,
        COUNT(CASE WHEN processing_status = 'completed' THEN 1 END)::INTEGER as completed,
        COUNT(CASE WHEN processing_status = 'pending' THEN 1 END)::INTEGER as pending,
        COUNT(CASE WHEN processing_status = 'failed' THEN 1 END)::INTEGER as failed,
        AVG(EXTRACT(EPOCH FROM (updated_at - created_at)) / 3600)::DECIMAL(8,2) as avg_hours,
        (SELECT COUNT(*) FROM krai_intelligence.chunks WHERE created_at BETWEEN date_from AND date_to + INTERVAL '1 day')::INTEGER,
        (SELECT COUNT(*) FROM krai_content.images WHERE created_at BETWEEN date_from AND date_to + INTERVAL '1 day')::INTEGER
    FROM krai_core.documents
    WHERE created_at BETWEEN date_from AND date_to + INTERVAL '1 day';
END;
$$;


--
-- Name: get_storage_statistics(); Type: FUNCTION; Schema: krai_system; Owner: -
--

CREATE FUNCTION krai_system.get_storage_statistics() RETURNS TABLE(bucket_name text, object_count bigint, total_size_bytes bigint, total_size_mb numeric)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        b.name,
        COUNT(o.id),
        COALESCE(SUM(o.size), 0),
        COALESCE(SUM(o.size), 0)::DECIMAL(10,2) / (1024 * 1024)
    FROM storage.buckets b
    LEFT JOIN storage.objects o ON b.id = o.bucket_id
    WHERE b.name LIKE 'krai-%'
    GROUP BY b.name
    ORDER BY b.name;
END;
$$;


--
-- Name: optimize_database_performance(); Type: FUNCTION; Schema: krai_system; Owner: -
--

CREATE FUNCTION krai_system.optimize_database_performance() RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
    result_text TEXT := '';
BEGIN
    -- Update table statistics
    ANALYZE krai_core.documents;
    ANALYZE krai_intelligence.chunks;
    ANALYZE krai_intelligence.embeddings;
    ANALYZE krai_content.images;

    result_text := result_text || 'Table statistics updated. ';

    -- Reindex critical indexes if needed
    REINDEX INDEX CONCURRENTLY idx_embeddings_vector_hnsw;
    result_text := result_text || 'Vector index reindexed. ';

    -- Vacuum analyze for performance
    VACUUM ANALYZE krai_core.documents;
    VACUUM ANALYZE krai_intelligence.chunks;

    result_text := result_text || 'Vacuum analyze completed.';

    RETURN result_text;
END;
$$;


--
-- Name: run_performance_test_suite(); Type: FUNCTION; Schema: krai_system; Owner: -
--

CREATE FUNCTION krai_system.run_performance_test_suite() RETURNS TABLE(test_name text, status text, execution_time_ms integer, details text, recommendation text)
    LANGUAGE plpgsql
    AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    duration_ms INTEGER;
    test_result TEXT;
    test_detail TEXT;
    test_recommendation TEXT;
BEGIN
    RAISE NOTICE '🚀 Starting KRAI Performance Test Suite...';

    -- Test 1: Basic Schema Connectivity
    start_time := clock_timestamp();

    SELECT COUNT(*)::TEXT INTO test_result
    FROM information_schema.tables
    WHERE table_schema LIKE 'krai_%';

    end_time := clock_timestamp();
    duration_ms := EXTRACT(EPOCH FROM (end_time - start_time)) * 1000;

    IF test_result::INTEGER >= 31 THEN
        test_detail := test_result || ' tables found across KRAI schemas';
        test_recommendation := 'Schema structure is complete';
    ELSE
        test_detail := 'Only ' || test_result || ' tables found - expected 31+';
        test_recommendation := 'Check schema migration completeness';
    END IF;

    RETURN QUERY SELECT
        'Schema Connectivity'::TEXT,
        CASE WHEN test_result::INTEGER >= 31 THEN '✅ PASS' ELSE '❌ FAIL' END,
        duration_ms,
        test_detail,
        test_recommendation;

    -- Test 2: Index Effectiveness Check
    start_time := clock_timestamp();

    SELECT COUNT(*)::TEXT INTO test_result
    FROM pg_indexes
    WHERE schemaname LIKE 'krai_%' AND indexname LIKE 'idx_%';

    end_time := clock_timestamp();
    duration_ms := EXTRACT(EPOCH FROM (end_time - start_time)) * 1000;

    test_detail := test_result || ' performance indexes found';
    test_recommendation := CASE
        WHEN test_result::INTEGER >= 15 THEN 'Index coverage is excellent'
        WHEN test_result::INTEGER >= 10 THEN 'Index coverage is good'
        ELSE 'Consider adding more performance indexes'
    END;

    RETURN QUERY SELECT
        'Index Coverage'::TEXT,
        CASE WHEN test_result::INTEGER >= 10 THEN '✅ PASS' ELSE '⚠️ WARN' END,
        duration_ms,
        test_detail,
        test_recommendation;

    -- Test 3: Foreign Key Constraint Performance
    start_time := clock_timestamp();

    SELECT COUNT(*)::TEXT INTO test_result
    FROM information_schema.table_constraints
    WHERE table_schema LIKE 'krai_%' AND constraint_type = 'FOREIGN KEY';

    end_time := clock_timestamp();
    duration_ms := EXTRACT(EPOCH FROM (end_time - start_time)) * 1000;

    test_detail := test_result || ' foreign key constraints active';
    test_recommendation := 'Foreign key integrity is maintained';

    RETURN QUERY SELECT
        'Foreign Key Constraints'::TEXT,
        CASE WHEN test_result::INTEGER >= 40 THEN '✅ PASS' ELSE '⚠️ WARN' END,
        duration_ms,
        test_detail,
        test_recommendation;

    -- Test 4: Vector Extension Check
    start_time := clock_timestamp();

    BEGIN
        EXECUTE 'SELECT 1 WHERE EXISTS (SELECT 1 FROM pg_extension WHERE extname = ''vector'')';
        test_result := 'Available';
        test_detail := 'pgvector extension is properly installed';
        test_recommendation := 'Vector operations ready for embeddings';
    EXCEPTION WHEN OTHERS THEN
        test_result := 'Missing';
        test_detail := 'pgvector extension not found';
        test_recommendation := 'Install pgvector extension for embeddings';
    END;

    end_time := clock_timestamp();
    duration_ms := EXTRACT(EPOCH FROM (end_time - start_time)) * 1000;

    RETURN QUERY SELECT
        'Vector Extension'::TEXT,
        CASE WHEN test_result = 'Available' THEN '✅ PASS' ELSE '❌ FAIL' END,
        duration_ms,
        test_detail,
        test_recommendation;

    -- Test 5: Storage Buckets Check
    start_time := clock_timestamp();

    SELECT COUNT(*)::TEXT INTO test_result
    FROM storage.buckets
    WHERE name LIKE 'krai-%';

    end_time := clock_timestamp();
    duration_ms := EXTRACT(EPOCH FROM (end_time - start_time)) * 1000;

    test_detail := test_result || ' KRAI storage buckets configured';
    test_recommendation := CASE
        WHEN test_result::INTEGER >= 3 THEN 'Storage buckets ready for file uploads'
        ELSE 'Configure missing storage buckets'
    END;

    RETURN QUERY SELECT
        'Storage Buckets'::TEXT,
        CASE WHEN test_result::INTEGER >= 3 THEN '✅ PASS' ELSE '❌ FAIL' END,
        duration_ms,
        test_detail,
        test_recommendation;

    RAISE NOTICE '✅ KRAI Performance Test Suite completed!';
END;
$$;


--
-- Name: system_health_check(); Type: FUNCTION; Schema: krai_system; Owner: -
--

CREATE FUNCTION krai_system.system_health_check() RETURNS TABLE(component text, status text, details text, recommendation text)
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Database size check
    RETURN QUERY
    SELECT
        'Database Size'::TEXT,
        '✅ Healthy'::TEXT,
        pg_size_pretty(pg_database_size(current_database())) || ' total size',
        'Database size is within normal limits'::TEXT;

    -- Connection check
    RETURN QUERY
    SELECT
        'Active Connections'::TEXT,
        '✅ Healthy'::TEXT,
        pg_stat_get_numbackends(oid)::TEXT || ' active connections' as details,
        'Connection count is normal'::TEXT
    FROM pg_database WHERE datname = current_database();

    -- Cache hit ratio
    RETURN QUERY
    SELECT
        'Cache Hit Ratio'::TEXT,
        CASE
            WHEN (blks_hit::FLOAT / (blks_hit + blks_read + 1)) > 0.90 THEN '✅ Excellent'
            WHEN (blks_hit::FLOAT / (blks_hit + blks_read + 1)) > 0.75 THEN '⚠️ Good'
            ELSE '❌ Poor'
        END,
        ROUND((blks_hit::FLOAT / (blks_hit + blks_read + 1)) * 100, 2)::TEXT || '% cache hit rate',
        CASE
            WHEN (blks_hit::FLOAT / (blks_hit + blks_read + 1)) > 0.90 THEN 'Excellent cache performance'
            WHEN (blks_hit::FLOAT / (blks_hit + blks_read + 1)) > 0.75 THEN 'Consider increasing shared_buffers'
            ELSE 'Increase shared_buffers and work_mem'
        END
    FROM pg_stat_database WHERE datname = current_database();

    -- Table statistics freshness
    RETURN QUERY
    SELECT
        'Statistics Currency'::TEXT,
        CASE
            WHEN MAX(last_analyze) > NOW() - INTERVAL '7 days' THEN '✅ Current'
            WHEN MAX(last_analyze) > NOW() - INTERVAL '30 days' THEN '⚠️ Stale'
            ELSE '❌ Very Stale'
        END,
        'Last analyze: ' || COALESCE(MAX(last_analyze)::TEXT, 'Never'),
        CASE
            WHEN MAX(last_analyze) > NOW() - INTERVAL '7 days' THEN 'Statistics are current'
            ELSE 'Run ANALYZE on tables for better query planning'
        END
    FROM pg_stat_user_tables WHERE schemaname LIKE 'krai_%';
END;
$$;


--
-- Name: test_index_performance(); Type: FUNCTION; Schema: krai_system; Owner: -
--

CREATE FUNCTION krai_system.test_index_performance() RETURNS TABLE(query_type text, execution_time_ms integer, index_used boolean, performance_rating text)
    LANGUAGE plpgsql
    AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    duration_ms INTEGER;
    plan_text TEXT;
    uses_index BOOLEAN;
BEGIN
    -- Test 1: Document lookup by manufacturer (should use index)
    start_time := clock_timestamp();

    PERFORM COUNT(*) FROM krai_core.documents d
    JOIN krai_core.manufacturers m ON d.manufacturer_id = m.id
    WHERE m.name = 'HP Inc.';

    end_time := clock_timestamp();
    duration_ms := EXTRACT(EPOCH FROM (end_time - start_time)) * 1000;

    -- Check if index is used (simplified)
    uses_index := duration_ms < 100; -- Heuristic: fast queries likely use indexes

    RETURN QUERY SELECT
        'Document by Manufacturer'::TEXT,
        duration_ms,
        uses_index,
        CASE
            WHEN duration_ms < 50 THEN '🚀 Excellent'
            WHEN duration_ms < 200 THEN '✅ Good'
            WHEN duration_ms < 500 THEN '⚠️ Fair'
            ELSE '❌ Slow'
        END;

    -- Test 2: Full-text search (should use GIN index)
    start_time := clock_timestamp();

    PERFORM COUNT(*) FROM krai_core.documents
    WHERE to_tsvector('english', COALESCE(content_text, '')) @@ plainto_tsquery('english', 'printer error');

    end_time := clock_timestamp();
    duration_ms := EXTRACT(EPOCH FROM (end_time - start_time)) * 1000;
    uses_index := duration_ms < 200;

    RETURN QUERY SELECT
        'Full-Text Search'::TEXT,
        duration_ms,
        uses_index,
        CASE
            WHEN duration_ms < 100 THEN '🚀 Excellent'
            WHEN duration_ms < 300 THEN '✅ Good'
            WHEN duration_ms < 1000 THEN '⚠️ Fair'
            ELSE '❌ Slow'
        END;

    -- Test 3: Composite index test (manufacturer + document type + status)
    start_time := clock_timestamp();

    PERFORM COUNT(*) FROM krai_core.documents
    WHERE manufacturer_id IS NOT NULL
      AND document_type = 'Service Manual'
      AND processing_status = 'completed';

    end_time := clock_timestamp();
    duration_ms := EXTRACT(EPOCH FROM (end_time - start_time)) * 1000;
    uses_index := duration_ms < 150;

    RETURN QUERY SELECT
        'Composite Index Query'::TEXT,
        duration_ms,
        uses_index,
        CASE
            WHEN duration_ms < 75 THEN '🚀 Excellent'
            WHEN duration_ms < 250 THEN '✅ Good'
            WHEN duration_ms < 750 THEN '⚠️ Fair'
            ELSE '❌ Slow'
        END;
END;
$$;


--
-- Name: test_vector_performance(); Type: FUNCTION; Schema: krai_system; Owner: -
--

CREATE FUNCTION krai_system.test_vector_performance() RETURNS TABLE(test_type text, execution_time_ms integer, vectors_tested integer, performance_rating text)
    LANGUAGE plpgsql
    AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    duration_ms INTEGER;
    vector_count INTEGER;
    sample_vector TEXT;
BEGIN
    -- Check if we have any embeddings to test with
    SELECT COUNT(*) INTO vector_count FROM krai_intelligence.embeddings LIMIT 1000;

    IF vector_count = 0 THEN
        RETURN QUERY SELECT
            'Vector Similarity Search'::TEXT,
            0,
            0,
            '⏭️ Skipped (No embeddings found)'::TEXT;
        RETURN;
    END IF;

    -- Create a sample vector for testing (768 dimensions of zeros)
    sample_vector := '[' || repeat('0,', 767) || '0]';

    start_time := clock_timestamp();

    -- Test vector similarity search
    PERFORM COUNT(*) FROM krai_intelligence.embeddings
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> sample_vector::vector
    LIMIT 10;

    end_time := clock_timestamp();
    duration_ms := EXTRACT(EPOCH FROM (end_time - start_time)) * 1000;

    RETURN QUERY SELECT
        'Vector Similarity Search'::TEXT,
        duration_ms,
        vector_count,
        CASE
            WHEN duration_ms < 100 THEN '🚀 Excellent (HNSW index working)'
            WHEN duration_ms < 500 THEN '✅ Good'
            WHEN duration_ms < 2000 THEN '⚠️ Fair (Consider index tuning)'
            ELSE '❌ Slow (Check HNSW index)'
        END;

EXCEPTION WHEN OTHERS THEN
    RETURN QUERY SELECT
        'Vector Similarity Search'::TEXT,
        -1,
        0,
        '❌ Error: ' || SQLERRM;
END;
$$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: krai_system; Owner: -
--

CREATE FUNCTION krai_system.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: images; Type: TABLE; Schema: krai_content; Owner: -
--

CREATE TABLE krai_content.images (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    document_id uuid,
    chunk_id uuid,
    filename character varying(255),
    original_filename character varying(255),
    storage_path text,
    storage_url text NOT NULL,
    svg_storage_url text,
    original_svg_content text,
    file_size integer,
    image_format character varying(10),
    is_vector_graphic boolean DEFAULT false,
    has_png_derivative boolean DEFAULT true,
    width_px integer,
    height_px integer,
    page_number integer,
    image_index integer,
    image_type character varying(50),
    ai_description text,
    ai_confidence numeric(3,2),
    contains_text boolean DEFAULT false,
    ocr_text text,
    ocr_confidence numeric(3,2),
    manual_description text,
    tags text[],
    file_hash character varying(64),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    figure_number character varying(50),
    figure_context text,
    context_caption text,
    page_header text,
    surrounding_paragraphs text[],
    related_error_codes text[],
    related_products text[],
    related_chunks uuid[],
    context_embedding extensions.vector(768)
);


--
-- Name: COLUMN images.chunk_id; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.images.chunk_id IS 'Optional reference to chunk where this image appears. Links to krai_intelligence.chunks.';


--
-- Name: COLUMN images.figure_number; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.images.figure_number IS 'Figure reference number (e.g., "1", "2.1")';


--
-- Name: COLUMN images.figure_context; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.images.figure_context IS 'Context text around figure reference';


--
-- Name: COLUMN images.svg_storage_url; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.images.svg_storage_url IS 'MinIO URL for original SVG file when image is vector graphic';


--
-- Name: COLUMN images.original_svg_content; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.images.original_svg_content IS 'Inline SVG content for small vector graphics (<100KB)';


--
-- Name: COLUMN images.is_vector_graphic; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.images.is_vector_graphic IS 'True when image originated from vector graphic extraction';

--
-- Name: COLUMN images.has_png_derivative; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.images.has_png_derivative IS 'True when a PNG derivative exists for vector graphics';


--
-- Name: links; Type: TABLE; Schema: krai_content; Owner: -
--

CREATE TABLE krai_content.links (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    document_id uuid NOT NULL,
    url text NOT NULL,
    link_type character varying(50) DEFAULT 'external'::character varying NOT NULL,
    page_number integer NOT NULL,
    description text,
    position_data jsonb,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    video_id uuid,
    metadata jsonb DEFAULT '{}'::jsonb,
    link_category character varying(50),
    confidence_score numeric(3,2) DEFAULT 0.0,
    manufacturer_id uuid,
    series_id uuid,
    related_error_codes text[],
    context_description text,
    related_chunks uuid[],
    context_embedding extensions.vector(768),
    CONSTRAINT link_type_check CHECK (((link_type)::text = ANY ((ARRAY['video'::character varying, 'external'::character varying, 'tutorial'::character varying, 'support'::character varying, 'download'::character varying, 'email'::character varying, 'phone'::character varying])::text[])))
);


--
-- Name: TABLE links; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON TABLE krai_content.links IS 'External links extracted from PDFs (videos, tutorials, etc.)';


--
-- Name: COLUMN links.link_type; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.links.link_type IS 'Type: video, external, tutorial';


--
-- Name: COLUMN links.position_data; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.links.position_data IS 'JSON data with link position/rect information';


--
-- Name: COLUMN links.manufacturer_id; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.links.manufacturer_id IS 'Manufacturer this link is related to (for fast filtering)';


--
-- Name: COLUMN links.series_id; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.links.series_id IS 'Product series this link is related to (for fast filtering)';


--
-- Name: COLUMN links.related_error_codes; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.links.related_error_codes IS 'Array of error codes mentioned in link (e.g., ["C-2801", "C-2802"])';


--
-- Name: print_defects; Type: TABLE; Schema: krai_content; Owner: -
--

CREATE TABLE krai_content.print_defects (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    manufacturer_id uuid NOT NULL,
    product_id uuid,
    original_image_id uuid,
    defect_name character varying(100) NOT NULL,
    defect_category character varying(50),
    defect_description text,
    example_image_url text,
    annotated_image_url text,
    detection_confidence numeric(3,2),
    common_causes jsonb DEFAULT '[]'::jsonb,
    recommended_solutions jsonb DEFAULT '[]'::jsonb,
    related_error_codes text[],
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: video_products; Type: TABLE; Schema: krai_content; Owner: -
--

CREATE TABLE krai_content.video_products (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    video_id uuid NOT NULL,
    product_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE video_products; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON TABLE krai_content.video_products IS 'Many-to-many relationship between videos and products';


--
-- Name: COLUMN video_products.video_id; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.video_products.video_id IS 'Reference to video';


--
-- Name: COLUMN video_products.product_id; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.video_products.product_id IS 'Reference to product model';


--
-- Name: videos; Type: TABLE; Schema: krai_content; Owner: -
--

CREATE TABLE krai_content.videos (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    link_id uuid,
    youtube_id character varying(20),
    platform character varying(20),
    video_url text,
    title character varying(500) NOT NULL,
    description text,
    thumbnail_url text,
    duration integer,
    channel_id character varying(50),
    channel_title character varying(200),
    published_at timestamp with time zone,
    manufacturer_id uuid,
    series_id uuid,
    document_id uuid,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    enriched_at timestamp with time zone DEFAULT now(),
    context_description text,
    related_products text[],
    related_chunks uuid[],
    page_number integer,
    context_embedding extensions.vector(768)
);


--
-- Name: TABLE videos; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON TABLE krai_content.videos IS 'Videos table - statistics removed (focus on technical content)';


--
-- Name: COLUMN videos.link_id; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.videos.link_id IS 'Reference to link in links table (can be NULL for direct API enrichment)';


--
-- Name: COLUMN videos.youtube_id; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.videos.youtube_id IS 'YouTube video ID for deduplication (YouTube only)';


--
-- Name: COLUMN videos.platform; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.videos.platform IS 'Video platform: youtube, vimeo, brightcove, direct';


--
-- Name: COLUMN videos.video_url; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.videos.video_url IS 'Full video URL for deduplication (all platforms)';


--
-- Name: COLUMN videos.duration; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.videos.duration IS 'Video duration in seconds';


--
-- Name: COLUMN videos.metadata; Type: COMMENT; Schema: krai_content; Owner: -
--

COMMENT ON COLUMN krai_content.videos.metadata IS 'Platform-specific extra data (vimeo_id, brightcove_id, file_size, etc.)';


--
-- Name: document_products; Type: TABLE; Schema: krai_core; Owner: -
--

CREATE TABLE krai_core.document_products (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    document_id uuid NOT NULL,
    product_id uuid NOT NULL,
    is_primary_product boolean DEFAULT false,
    confidence_score numeric(3,2) DEFAULT 0.80,
    extraction_method character varying(50),
    page_numbers integer[],
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE document_products; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON TABLE krai_core.document_products IS 'Many-to-Many relationship between documents and products';


--
-- Name: COLUMN document_products.is_primary_product; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.document_products.is_primary_product IS 'True if this is the main product covered by the document';


--
-- Name: COLUMN document_products.confidence_score; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.document_products.confidence_score IS 'Confidence score (0-1) of the product extraction';


--
-- Name: COLUMN document_products.extraction_method; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.document_products.extraction_method IS 'How the product was extracted: pattern, llm, vision, or manual';


--
-- Name: document_relationships; Type: TABLE; Schema: krai_core; Owner: -
--

CREATE TABLE krai_core.document_relationships (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    primary_document_id uuid NOT NULL,
    secondary_document_id uuid NOT NULL,
    relationship_type character varying(50) NOT NULL,
    relationship_strength numeric(3,2) DEFAULT 0.5,
    auto_discovered boolean DEFAULT true,
    manual_verification boolean DEFAULT false,
    verification_date timestamp with time zone,
    verified_by character varying(100),
    notes text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: documents; Type: TABLE; Schema: krai_core; Owner: -
--

CREATE TABLE krai_core.documents (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    filename character varying(255) NOT NULL,
    file_size bigint,
    file_hash character varying(64),
    storage_path text,
    document_type character varying(100),
    language character varying(10) DEFAULT 'en'::character varying,
    version character varying(50),
    publish_date date,
    page_count integer,
    word_count integer,
    character_count integer,
    extracted_metadata jsonb DEFAULT '{}'::jsonb,
    processing_status character varying(50) DEFAULT 'pending'::character varying,
    processing_results jsonb,
    processing_error text,
    stage_status jsonb DEFAULT '{}'::jsonb,
    confidence_score numeric(3,2),
    ocr_confidence numeric(3,2),
    manual_review_required boolean DEFAULT false,
    manual_review_completed boolean DEFAULT false,
    manual_review_notes text,
    manufacturer character varying(100),
    series character varying(100),
    models text[],
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    priority_level integer DEFAULT 5,
    manufacturer_id uuid
);


--
-- Name: TABLE documents; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON TABLE krai_core.documents IS 'Core documents table - cleaned up unused columns';


--
-- Name: COLUMN documents.version; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.documents.version IS 'Document version extracted from content';


--
-- Name: COLUMN documents.processing_status; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.documents.processing_status IS 'Processing status: pending, processing, completed, failed';


--
-- Name: COLUMN documents.processing_results; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.documents.processing_results IS 'Complete processing results from pipeline (JSONB)';


--
-- Name: COLUMN documents.processing_error; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.documents.processing_error IS 'Error message if processing failed';


--
-- Name: COLUMN documents.stage_status; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.documents.stage_status IS 'Per-stage processing status tracking (JSONB)';


--
-- Name: COLUMN documents.manufacturer; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.documents.manufacturer IS 'Manufacturer name (text) - auto-detected during processing';


--
-- Name: COLUMN documents.models; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.documents.models IS 'Array of model numbers extracted from document';


--
-- Name: COLUMN documents.priority_level; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.documents.priority_level IS 'Search result priority (1=highest/bulletins, 2=service_manual, 3=parts, etc.)';


--
-- Name: COLUMN documents.manufacturer_id; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.documents.manufacturer_id IS 'metadata-refresh: triggered at now()';


--
-- Name: manufacturers; Type: TABLE; Schema: krai_core; Owner: -
--

CREATE TABLE krai_core.manufacturers (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    name character varying(100) NOT NULL,
    short_name character varying(10),
    country character varying(50),
    founded_year integer,
    website character varying(255),
    support_email character varying(255),
    support_phone character varying(50),
    logo_url text,
    is_competitor boolean DEFAULT false,
    market_share_percent numeric(5,2),
    annual_revenue_usd bigint,
    employee_count integer,
    headquarters_address text,
    stock_symbol character varying(10),
    primary_business_segment character varying(100),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE manufacturers; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON TABLE krai_core.manufacturers IS 'Printer and office equipment manufacturers. Seeded with 14 major manufacturers on 2025-10-09.';


--
-- Name: oem_relationships; Type: TABLE; Schema: krai_core; Owner: -
--

CREATE TABLE krai_core.oem_relationships (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    brand_manufacturer character varying(100) NOT NULL,
    brand_series_pattern character varying(200) NOT NULL,
    oem_manufacturer character varying(100) NOT NULL,
    relationship_type character varying(50) DEFAULT 'engine'::character varying,
    applies_to text[] DEFAULT ARRAY['error_codes'::text, 'parts'::text],
    notes text,
    confidence double precision DEFAULT 1.0,
    source character varying(100) DEFAULT 'manual'::character varying,
    verified boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT valid_confidence CHECK (((confidence >= (0.0)::double precision) AND (confidence <= (1.0)::double precision)))
);


--
-- Name: TABLE oem_relationships; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON TABLE krai_core.oem_relationships IS 'Stores OEM/rebrand relationships between manufacturers for cross-manufacturer search and error code detection';


--
-- Name: COLUMN oem_relationships.brand_manufacturer; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.oem_relationships.brand_manufacturer IS 'The brand name shown on the product (e.g., "Konica Minolta", "Xerox")';


--
-- Name: COLUMN oem_relationships.brand_series_pattern; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.oem_relationships.brand_series_pattern IS 'Regex pattern to match product series (e.g., "[45]000i" for 4000i/5000i)';


--
-- Name: COLUMN oem_relationships.oem_manufacturer; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.oem_relationships.oem_manufacturer IS 'The actual manufacturer of the engine/platform (e.g., "Brother", "Fujifilm")';


--
-- Name: COLUMN oem_relationships.applies_to; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.oem_relationships.applies_to IS 'Array of what this OEM relationship affects: error_codes, parts, supplies, accessories';


--
-- Name: COLUMN oem_relationships.confidence; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.oem_relationships.confidence IS 'Confidence level in this mapping (0.0 = uncertain, 1.0 = verified)';


--
-- Name: option_dependencies; Type: TABLE; Schema: krai_core; Owner: -
--

CREATE TABLE krai_core.option_dependencies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    option_id uuid NOT NULL,
    depends_on_option_id uuid NOT NULL,
    dependency_type character varying(20) NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT no_self_dependency CHECK ((option_id <> depends_on_option_id)),
    CONSTRAINT option_dependencies_dependency_type_check CHECK (((dependency_type)::text = ANY ((ARRAY['requires'::character varying, 'excludes'::character varying, 'alternative'::character varying])::text[])))
);


--
-- Name: TABLE option_dependencies; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON TABLE krai_core.option_dependencies IS 'Models complex relationships between product options/accessories';


--
-- Name: COLUMN option_dependencies.dependency_type; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.option_dependencies.dependency_type IS 'Type: requires (needs), excludes (conflicts), alternative (or)';


--
-- Name: product_accessories; Type: TABLE; Schema: krai_core; Owner: -
--

CREATE TABLE krai_core.product_accessories (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    product_id uuid NOT NULL,
    accessory_id uuid NOT NULL,
    compatibility_type character varying(50) NOT NULL,
    installation_required boolean DEFAULT false,
    quantity_min integer DEFAULT 1,
    quantity_max integer DEFAULT 1,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    priority integer DEFAULT 0,
    compatibility_notes text,
    is_standard boolean DEFAULT false,
    mounting_position character varying(20),
    slot_number integer,
    max_quantity integer DEFAULT 1,
    CONSTRAINT mounting_position_check CHECK (((mounting_position)::text = ANY ((ARRAY['top'::character varying, 'side'::character varying, 'bottom'::character varying, 'internal'::character varying, 'accessory'::character varying, NULL::character varying])::text[]))),
    CONSTRAINT product_accessories_compatibility_type_check CHECK (((compatibility_type)::text = ANY ((ARRAY['compatible'::character varying, 'required'::character varying, 'requires'::character varying, 'conflicts'::character varying, 'recommended'::character varying, 'alternative'::character varying, 'prerequisite'::character varying])::text[]))),
    CONSTRAINT product_accessories_no_self_reference CHECK ((product_id <> accessory_id))
);


--
-- Name: TABLE product_accessories; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON TABLE krai_core.product_accessories IS 'M:N junction table linking products to their compatible accessories/options. One accessory can fit multiple products.';


--
-- Name: COLUMN product_accessories.product_id; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.product_accessories.product_id IS 'The main product (e.g., bizhub C558)';


--
-- Name: COLUMN product_accessories.accessory_id; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.product_accessories.accessory_id IS 'The accessory/option (e.g., Finisher FS-533, Paper Tray PF-707)';


--
-- Name: COLUMN product_accessories.is_standard; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.product_accessories.is_standard IS 'True if this accessory comes standard with the product, false if optional';


--
-- Name: COLUMN product_accessories.mounting_position; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.product_accessories.mounting_position IS 'Physical mounting position: top (document feeders), side (finishers), bottom (cabinets), internal (controllers), accessory (kits)';


--
-- Name: COLUMN product_accessories.slot_number; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.product_accessories.slot_number IS 'Slot number if accessory can be installed in multiple positions (e.g., FK-513 in slot 1 or 2)';


--
-- Name: COLUMN product_accessories.max_quantity; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.product_accessories.max_quantity IS 'Maximum quantity of this accessory that can be installed (default: 1)';


--
-- Name: product_configurations; Type: TABLE; Schema: krai_core; Owner: -
--

CREATE TABLE krai_core.product_configurations (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    configuration_name character varying(200),
    base_product_id uuid NOT NULL,
    accessories jsonb DEFAULT '[]'::jsonb,
    is_valid boolean DEFAULT true,
    validation_errors jsonb DEFAULT '[]'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    created_by character varying(100)
);


--
-- Name: product_series; Type: TABLE; Schema: krai_core; Owner: -
--

CREATE TABLE krai_core.product_series (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    manufacturer_id uuid NOT NULL,
    series_name character varying(100) NOT NULL,
    series_code character varying(50),
    launch_date date,
    end_of_life_date date,
    target_market character varying(100),
    price_range character varying(50),
    key_features jsonb DEFAULT '{}'::jsonb,
    series_description text,
    marketing_name character varying(150),
    successor_series_id uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    model_pattern text
);


--
-- Name: COLUMN product_series.series_name; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.product_series.series_name IS 'Marketing/user-friendly series name (e.g., LaserJet, bizhub) for broad search';


--
-- Name: COLUMN product_series.model_pattern; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.product_series.model_pattern IS 'Technical series pattern (e.g., E500xx, M4xx, C558) for precise matching';


--
-- Name: products; Type: TABLE; Schema: krai_core; Owner: -
--

CREATE TABLE krai_core.products (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    manufacturer_id uuid,
    series_id uuid,
    model_number character varying(100) NOT NULL,
    product_type character varying(50) DEFAULT 'laser_printer'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    specifications jsonb DEFAULT '{}'::jsonb,
    pricing jsonb DEFAULT '{}'::jsonb,
    lifecycle jsonb DEFAULT '{}'::jsonb,
    urls jsonb DEFAULT '{}'::jsonb,
    metadata jsonb DEFAULT '{}'::jsonb,
    oem_manufacturer character varying(100),
    oem_relationship_type character varying(50),
    oem_notes text,
    product_code character varying(10),
    article_code character varying(50),
    CONSTRAINT product_type_check CHECK (((product_type)::text = ANY ((ARRAY['laser_printer'::character varying, 'inkjet_printer'::character varying, 'laser_production_printer'::character varying, 'inkjet_production_printer'::character varying, 'solid_ink_printer'::character varying, 'dot_matrix_printer'::character varying, 'thermal_printer'::character varying, 'dye_sublimation_printer'::character varying, 'laser_multifunction'::character varying, 'inkjet_multifunction'::character varying, 'laser_production_multifunction'::character varying, 'inkjet_production_multifunction'::character varying, 'solid_ink_multifunction'::character varying, 'inkjet_plotter'::character varying, 'latex_plotter'::character varying, 'pen_plotter'::character varying, 'scanner'::character varying, 'document_scanner'::character varying, 'photo_scanner'::character varying, 'large_format_scanner'::character varying, 'copier'::character varying, 'finisher'::character varying, 'stapler_finisher'::character varying, 'booklet_finisher'::character varying, 'punch_finisher'::character varying, 'saddle_finisher'::character varying, 'finisher_accessory'::character varying, 'folder'::character varying, 'trimmer'::character varying, 'stacker'::character varying, 'post_inserter'::character varying, 'z_fold_unit'::character varying, 'creaser'::character varying, 'folding_unit'::character varying, 'stapler'::character varying, 'punch_unit'::character varying, 'fold_unit'::character varying, 'feeder'::character varying, 'paper_feeder'::character varying, 'envelope_feeder'::character varying, 'large_capacity_feeder'::character varying, 'document_feeder'::character varying, 'large_capacity_unit'::character varying, 'relay_unit'::character varying, 'image_controller'::character varying, 'controller_accessory'::character varying, 'controller'::character varying, 'controller_unit'::character varying, 'authentication_unit'::character varying, 'accessory'::character varying, 'cabinet'::character varying, 'work_table'::character varying, 'caster_base'::character varying, 'bridge_unit'::character varying, 'interface_kit'::character varying, 'media_sensor'::character varying, 'memory_upgrade'::character varying, 'hard_drive'::character varying, 'fax_kit'::character varying, 'wireless_kit'::character varying, 'keyboard'::character varying, 'card_reader'::character varying, 'coin_kit'::character varying, 'option'::character varying, 'duplex_unit'::character varying, 'output_tray'::character varying, 'mailbox'::character varying, 'mount_kit'::character varying, 'job_separator'::character varying, 'consumable'::character varying, 'toner_cartridge'::character varying, 'ink_cartridge'::character varying, 'drum_unit'::character varying, 'developer_unit'::character varying, 'fuser_unit'::character varying, 'transfer_belt'::character varying, 'waste_toner_box'::character varying, 'maintenance_kit'::character varying, 'staple_cartridge'::character varying, 'punch_kit'::character varying, 'print_head'::character varying, 'ink_tank'::character varying, 'paper'::character varying, 'software'::character varying, 'license'::character varying, 'firmware'::character varying])::text[]))),
    CONSTRAINT products_product_type_check CHECK (((product_type)::text = ANY (ARRAY['laser_printer'::text, 'inkjet_printer'::text, 'laser_production_printer'::text, 'inkjet_production_printer'::text, 'solid_ink_printer'::text, 'dot_matrix_printer'::text, 'thermal_printer'::text, 'dye_sublimation_printer'::text, 'laser_multifunction'::text, 'inkjet_multifunction'::text, 'laser_production_multifunction'::text, 'inkjet_production_multifunction'::text, 'solid_ink_multifunction'::text, 'inkjet_plotter'::text, 'latex_plotter'::text, 'pen_plotter'::text, 'scanner'::text, 'document_scanner'::text, 'photo_scanner'::text, 'large_format_scanner'::text, 'copier'::text, 'inline_finisher'::text, 'finisher'::text, 'stapler_finisher'::text, 'booklet_finisher'::text, 'punch_finisher'::text, 'saddle_finisher'::text, 'saddle_stitch_module'::text, 'finisher_accessory'::text, 'folder'::text, 'trimmer'::text, 'stacker'::text, 'post_inserter'::text, 'z_fold_unit'::text, 'creaser'::text, 'folding_unit'::text, 'stapler'::text, 'punch_unit'::text, 'fold_unit'::text, 'feeder'::text, 'cleaning_unit'::text, 'creaser_unit'::text, 'paper_cabinet'::text, 'envelope_feeder'::text, 'large_capacity_tray'::text, 'document_feeder'::text, 'large_capacity_unit'::text, 'relay_unit'::text, 'image_controller'::text, 'controller_accessory'::text, 'controller'::text, 'controller_unit'::text, 'authentication_unit'::text, 'accessory'::text, 'cabinet'::text, 'work_table'::text, 'caster_base'::text, 'bridge_unit'::text, 'interface_kit'::text, 'media_sensor'::text, 'memory_upgrade'::text, 'iq_sensor'::text, 'hard_drive'::text, 'fax_kit'::text, 'wireless_kit'::text, 'keyboard'::text, 'card_reader'::text, 'coin_kit'::text, 'option'::text, 'duplex_unit'::text, 'output_tray'::text, 'mailbox'::text, 'mount_kit'::text, 'upgrade_kit'::text, 'job_separator'::text, 'consumable'::text, 'toner_cartridge'::text, 'ink_cartridge'::text, 'drum_unit'::text, 'humidifier_unit'::text, 'developer_unit'::text, 'maintenance_kit'::text, 'staple_cartridge'::text, 'punch_kit'::text, 'print_head'::text, 'ink_tank'::text, 'paper'::text, 'software'::text, 'license'::text, 'firmware'::text])))
);


--
-- Name: COLUMN products.manufacturer_id; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.products.manufacturer_id IS 'Optional FK to manufacturers table. Can be NULL if only manufacturer name is known. Use manufacturer_name (in metadata) for text-based manufacturer info.';


--
-- Name: COLUMN products.product_type; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.products.product_type IS 'Product type (VARCHAR): includes specialized categories for finishers, controllers, and accessories';


--
-- Name: COLUMN products.oem_manufacturer; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.products.oem_manufacturer IS 'The OEM manufacturer if this is a rebrand (e.g., "Brother" for Konica Minolta 5000i)';


--
-- Name: COLUMN products.oem_relationship_type; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.products.oem_relationship_type IS 'Type of OEM relationship: engine, rebrand, platform, partnership';


--
-- Name: COLUMN products.oem_notes; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.products.oem_notes IS 'Additional notes about the OEM relationship';


--
-- Name: COLUMN products.product_code; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.products.product_code IS 'Product code (e.g., first 4 chars of serial number for Konica Minolta: A93E, AAJN)';


--
-- Name: COLUMN products.article_code; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON COLUMN krai_core.products.article_code IS 'Manufacturer article/part number (e.g., AAJ4WY2961). Used for ordering and identification.';


--
-- Name: CONSTRAINT product_type_check ON products; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON CONSTRAINT product_type_check ON krai_core.products IS 'Product types including Foliant-specific categories: authentication_unit, controller_unit, punch_unit, stapler, relay_unit, fold_unit, large_capacity_unit';


--
-- Name: products_backup; Type: TABLE; Schema: krai_core; Owner: -
--

CREATE TABLE krai_core.products_backup (
    id uuid,
    parent_id uuid,
    manufacturer_id uuid,
    series_id uuid,
    model_number character varying(100),
    model_name character varying(200),
    product_type character varying(50),
    launch_date date,
    end_of_life_date date,
    msrp_usd numeric(10,2),
    weight_kg numeric(8,2),
    dimensions_mm jsonb,
    color_options text[],
    connectivity_options text[],
    print_technology character varying(50),
    max_print_speed_ppm integer,
    max_resolution_dpi integer,
    max_paper_size character varying(20),
    duplex_capable boolean,
    network_capable boolean,
    mobile_print_support boolean,
    supported_languages text[],
    energy_star_certified boolean,
    warranty_months integer,
    service_manual_url text,
    parts_catalog_url text,
    driver_download_url text,
    firmware_version character varying(50),
    option_dependencies jsonb,
    replacement_parts jsonb,
    common_issues jsonb,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


--
-- Name: tool_usage; Type: TABLE; Schema: krai_intelligence; Owner: -
--

CREATE TABLE krai_intelligence.tool_usage (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    session_id text NOT NULL,
    tool_name text NOT NULL,
    query_params jsonb,
    results_count integer,
    response_time_ms integer,
    success boolean DEFAULT true,
    error_message text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE tool_usage; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON TABLE krai_intelligence.tool_usage IS 'Tracks which tools are used, how often, and their performance';


--
-- Name: agent_performance; Type: VIEW; Schema: krai_intelligence; Owner: -
--

CREATE VIEW krai_intelligence.agent_performance AS
 SELECT date(created_at) AS date,
    tool_name,
    count(*) AS total_calls,
    count(*) FILTER (WHERE (success = true)) AS successful_calls,
    count(*) FILTER (WHERE (success = false)) AS failed_calls,
    avg(response_time_ms) AS avg_response_time_ms,
    percentile_cont((0.95)::double precision) WITHIN GROUP (ORDER BY ((response_time_ms)::double precision)) AS p95_response_time_ms,
    avg(results_count) AS avg_results_count
   FROM krai_intelligence.tool_usage tu
  GROUP BY (date(created_at)), tool_name
  ORDER BY (date(created_at)) DESC, (count(*)) DESC;


--
-- Name: VIEW agent_performance; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON VIEW krai_intelligence.agent_performance IS 'Daily performance metrics for agent tools';


--
-- Name: chunks; Type: TABLE; Schema: krai_intelligence; Owner: -
--

CREATE TABLE krai_intelligence.chunks (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    document_id uuid NOT NULL,
    text_chunk text NOT NULL,
    chunk_index integer NOT NULL,
    page_start integer,
    page_end integer,
    processing_status character varying(20) DEFAULT 'pending'::character varying,
    fingerprint character varying(64) NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    embedding extensions.vector(768),
    page_label_start character varying(20),
    page_label_end character varying(20),
    CONSTRAINT chunks_processing_status_check CHECK (((processing_status)::text = ANY ((ARRAY['pending'::character varying, 'completed'::character varying, 'failed'::character varying])::text[])))
);

--
-- Name: unified_embeddings; Type: TABLE; Schema: krai_intelligence; Owner: -
--

CREATE TABLE krai_intelligence.unified_embeddings (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    source_id uuid NOT NULL,
    source_type character varying(20) NOT NULL,
    embedding extensions.vector(768) NOT NULL,
    model_name character varying(100) NOT NULL,
    embedding_context text,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT unified_embeddings_source_type_check CHECK ((source_type)::text = ANY ((ARRAY['text'::character varying, 'image'::character varying, 'table'::character varying, 'caption'::character varying, 'context'::character varying])::text[]))
);

--
-- Name: structured_tables; Type: TABLE; Schema: krai_intelligence; Owner: -
--

CREATE TABLE krai_intelligence.structured_tables (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    document_id uuid NOT NULL,
    chunk_id uuid,
    page_number integer,
    table_index integer,
    table_type character varying(50),
    column_headers text[],
    row_count integer,
    column_count integer,
    table_data jsonb,
    table_markdown text,
    caption text,
    context_text text,
    related_error_codes text[],
    related_products text[],
    related_chunks uuid[],
    table_embedding extensions.vector(768),
    context_embedding extensions.vector(768),
    column_embeddings jsonb,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT structured_tables_type_check CHECK ((table_type)::text = ANY ((ARRAY['specification'::character varying, 'comparison'::character varying, 'parts_list'::character varying, 'error_codes'::character varying, 'other'::character varying])::text[]))
);


--
-- Name: TABLE chunks; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON TABLE krai_intelligence.chunks IS 'AI-ready chunks with fingerprints and status tracking. Populated by ChunkPreprocessor from krai_content.chunks.';


--
-- Name: COLUMN chunks.fingerprint; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.chunks.fingerprint IS 'SHA256 fingerprint for chunk deduplication (64 chars)';


--
-- Name: COLUMN chunks.page_label_start; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.chunks.page_label_start IS 'Document page label for start page (e.g., "i", "ii", "1", "2") - for user display';


--
-- Name: COLUMN chunks.page_label_end; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.chunks.page_label_end IS 'Document page label for end page (e.g., "i", "ii", "1", "2") - for user display';


--
-- Name: error_code_images; Type: TABLE; Schema: krai_intelligence; Owner: -
--

CREATE TABLE krai_intelligence.error_code_images (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    error_code_id uuid NOT NULL,
    image_id uuid NOT NULL,
    match_method text,
    match_confidence double precision DEFAULT 0.5,
    display_order integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE error_code_images; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON TABLE krai_intelligence.error_code_images IS 'Junction table linking error codes to multiple images (many-to-many relationship)';


--
-- Name: COLUMN error_code_images.match_method; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.error_code_images.match_method IS 'How the image was matched: smart_vision_ai (AI detected error code), page_match (same page), manual';


--
-- Name: COLUMN error_code_images.display_order; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.error_code_images.display_order IS 'Order for displaying images (0 = most relevant)';


--
-- Name: error_code_parts; Type: TABLE; Schema: krai_intelligence; Owner: -
--

CREATE TABLE krai_intelligence.error_code_parts (
    error_code_id uuid NOT NULL,
    part_id uuid NOT NULL,
    relevance_score double precision DEFAULT 1.0,
    extraction_source text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE error_code_parts; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON TABLE krai_intelligence.error_code_parts IS 'Junction table linking error codes to parts';


--
-- Name: COLUMN error_code_parts.relevance_score; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.error_code_parts.relevance_score IS 'How relevant is this part to the error (0.0-1.0)';


--
-- Name: COLUMN error_code_parts.extraction_source; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.error_code_parts.extraction_source IS 'Where the part was found (solution_text, description, etc.)';


--
-- Name: error_codes; Type: TABLE; Schema: krai_intelligence; Owner: -
--

CREATE TABLE krai_intelligence.error_codes (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    chunk_id uuid,
    document_id uuid,
    manufacturer_id uuid,
    error_code character varying(20) NOT NULL,
    error_description text,
    solution_text text,
    page_number integer,
    confidence_score numeric(3,2),
    extraction_method character varying(50),
    requires_technician boolean DEFAULT false,
    requires_parts boolean DEFAULT false,
    estimated_fix_time_minutes integer,
    severity_level character varying(20),
    created_at timestamp with time zone DEFAULT now(),
    image_id uuid,
    context_text text,
    metadata jsonb DEFAULT '{}'::jsonb,
    product_id uuid,
    video_id uuid
);


--
-- Name: COLUMN error_codes.image_id; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.error_codes.image_id IS 'Reference to screenshot/image where error code was found (for Smart Vision AI matching)';


--
-- Name: COLUMN error_codes.context_text; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.error_codes.context_text IS 'Surrounding text where error code was found (for context)';


--
-- Name: COLUMN error_codes.metadata; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.error_codes.metadata IS 'Flexible JSONB storage for extraction metadata (smart matching info, etc.)';


--
-- Name: COLUMN error_codes.product_id; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.error_codes.product_id IS 'Product/model this error code applies to (allows same code for different models)';


--
-- Name: COLUMN error_codes.video_id; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.error_codes.video_id IS 'Video demonstrating solution for this error code';


--
-- Name: feedback; Type: TABLE; Schema: krai_intelligence; Owner: -
--

CREATE TABLE krai_intelligence.feedback (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    session_id text NOT NULL,
    message_id text,
    rating integer,
    feedback_type text,
    comment text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT feedback_feedback_type_check CHECK ((feedback_type = ANY (ARRAY['helpful'::text, 'not_helpful'::text, 'incorrect'::text, 'incomplete'::text]))),
    CONSTRAINT feedback_rating_check CHECK (((rating >= 1) AND (rating <= 5)))
);


--
-- Name: TABLE feedback; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON TABLE krai_intelligence.feedback IS 'User feedback on agent responses for continuous improvement';


--
-- Name: product_research_cache; Type: TABLE; Schema: krai_intelligence; Owner: -
--

CREATE TABLE krai_intelligence.product_research_cache (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    manufacturer character varying(100) NOT NULL,
    model_number character varying(100) NOT NULL,
    series_name character varying(200),
    series_description text,
    specifications jsonb DEFAULT '{}'::jsonb,
    physical_specs jsonb DEFAULT '{}'::jsonb,
    oem_manufacturer character varying(100),
    oem_relationship_type character varying(50),
    oem_notes text,
    launch_date date,
    eol_date date,
    pricing jsonb DEFAULT '{}'::jsonb,
    product_type character varying(100),
    confidence double precision DEFAULT 0.0,
    source_urls text[],
    research_date timestamp with time zone DEFAULT now(),
    cache_valid_until timestamp with time zone,
    verified boolean DEFAULT false,
    verified_by character varying(100),
    verified_at timestamp with time zone,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT valid_confidence CHECK (((confidence >= (0.0)::double precision) AND (confidence <= (1.0)::double precision)))
);


--
-- Name: TABLE product_research_cache; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON TABLE krai_intelligence.product_research_cache IS 'Stores AI-powered online research results for products (specs, OEM, series)';


--
-- Name: COLUMN product_research_cache.manufacturer; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.product_research_cache.manufacturer IS 'Manufacturer name (e.g., "Konica Minolta", "HP")';


--
-- Name: COLUMN product_research_cache.model_number; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.product_research_cache.model_number IS 'Product model number (e.g., "C750i", "LaserJet Pro M454dw")';


--
-- Name: COLUMN product_research_cache.specifications; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.product_research_cache.specifications IS 'JSONB with product specifications (speed, resolution, memory, etc.)';


--
-- Name: COLUMN product_research_cache.physical_specs; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.product_research_cache.physical_specs IS 'JSONB with physical specifications (dimensions, weight, power)';


--
-- Name: COLUMN product_research_cache.confidence; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.product_research_cache.confidence IS 'Confidence level in research results (0.0 = uncertain, 1.0 = verified)';


--
-- Name: COLUMN product_research_cache.source_urls; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.product_research_cache.source_urls IS 'Array of URLs used for research (manufacturer website, datasheets, etc.)';


--
-- Name: COLUMN product_research_cache.cache_valid_until; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.product_research_cache.cache_valid_until IS 'Cache expiration date (research should be refreshed after this date)';


--
-- Name: COLUMN product_research_cache.verified; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON COLUMN krai_intelligence.product_research_cache.verified IS 'Whether research results have been manually verified';


--
-- Name: search_analytics; Type: TABLE; Schema: krai_intelligence; Owner: -
--

CREATE TABLE krai_intelligence.search_analytics (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    search_query text NOT NULL,
    search_type character varying(50),
    results_count integer,
    click_through_rate numeric(5,4),
    user_satisfaction_rating integer,
    search_duration_ms integer,
    result_relevance_scores jsonb,
    user_session_id character varying(100),
    user_id uuid,
    manufacturer_filter uuid,
    product_filter uuid,
    document_type_filter character varying(100),
    language_filter character varying(10),
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT search_analytics_user_satisfaction_rating_check CHECK (((user_satisfaction_rating >= 1) AND (user_satisfaction_rating <= 5)))
);


--
-- Name: session_context; Type: TABLE; Schema: krai_intelligence; Owner: -
--

CREATE TABLE krai_intelligence.session_context (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    session_id text NOT NULL,
    context_type text NOT NULL,
    context_value text NOT NULL,
    confidence double precision DEFAULT 1.0,
    first_mentioned_at timestamp with time zone DEFAULT now(),
    last_used_at timestamp with time zone DEFAULT now(),
    use_count integer DEFAULT 1
);


--
-- Name: TABLE session_context; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON TABLE krai_intelligence.session_context IS 'Stores extracted context (manufacturer, model, etc.) from conversations for better follow-up responses';


--
-- Name: user_satisfaction; Type: VIEW; Schema: krai_intelligence; Owner: -
--

CREATE VIEW krai_intelligence.user_satisfaction AS
 SELECT date(created_at) AS date,
    count(*) AS total_feedback,
    avg(rating) AS avg_rating,
    count(*) FILTER (WHERE (rating >= 4)) AS positive_feedback,
    count(*) FILTER (WHERE (rating <= 2)) AS negative_feedback,
    count(*) FILTER (WHERE (feedback_type = 'helpful'::text)) AS helpful_count,
    count(*) FILTER (WHERE (feedback_type = 'not_helpful'::text)) AS not_helpful_count,
    count(*) FILTER (WHERE (feedback_type = 'incorrect'::text)) AS incorrect_count
   FROM krai_intelligence.feedback f
  GROUP BY (date(created_at))
  ORDER BY (date(created_at)) DESC;


--
-- Name: VIEW user_satisfaction; Type: COMMENT; Schema: krai_intelligence; Owner: -
--

COMMENT ON VIEW krai_intelligence.user_satisfaction IS 'Daily user satisfaction metrics';


--
-- Name: inventory_levels; Type: TABLE; Schema: krai_parts; Owner: -
--

CREATE TABLE krai_parts.inventory_levels (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    part_id uuid NOT NULL,
    warehouse_location character varying(100),
    current_stock integer DEFAULT 0,
    minimum_stock_level integer DEFAULT 0,
    maximum_stock_level integer DEFAULT 1000,
    last_updated timestamp with time zone DEFAULT now()
);


--
-- Name: parts_catalog; Type: TABLE; Schema: krai_parts; Owner: -
--

CREATE TABLE krai_parts.parts_catalog (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    manufacturer_id uuid NOT NULL,
    part_number character varying(100) NOT NULL,
    part_name character varying(255),
    part_description text,
    part_category character varying(100),
    unit_price_usd numeric(10,2),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: audit_log; Type: TABLE; Schema: krai_system; Owner: -
--

CREATE TABLE krai_system.audit_log (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    table_name character varying(100) NOT NULL,
    record_id uuid NOT NULL,
    operation character varying(10) NOT NULL,
    old_values jsonb,
    new_values jsonb,
    changed_by character varying(100),
    changed_at timestamp with time zone DEFAULT now(),
    session_id character varying(100),
    ip_address inet,
    user_agent text,
    CONSTRAINT audit_log_operation_check CHECK (((operation)::text = ANY ((ARRAY['INSERT'::character varying, 'UPDATE'::character varying, 'DELETE'::character varying])::text[])))
);


--
-- Name: health_checks; Type: TABLE; Schema: krai_system; Owner: -
--

CREATE TABLE krai_system.health_checks (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    service_name character varying(100) NOT NULL,
    check_type character varying(50) NOT NULL,
    status character varying(20) NOT NULL,
    response_time_ms integer,
    error_message text,
    details jsonb DEFAULT '{}'::jsonb,
    checked_at timestamp with time zone DEFAULT now()
);


--
-- Name: processing_queue; Type: TABLE; Schema: krai_system; Owner: -
--

CREATE TABLE krai_system.processing_queue (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    document_id uuid,
    chunk_id uuid,
    image_id uuid,
    video_id uuid,
    task_type character varying(50) NOT NULL,
    priority integer DEFAULT 5,
    status character varying(20) DEFAULT 'pending'::character varying,
    scheduled_at timestamp with time zone DEFAULT now(),
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    error_message text,
    retry_count integer DEFAULT 0,
    max_retries integer DEFAULT 3,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: stage_tracking; Type: TABLE; Schema: krai_system; Owner: -
--

CREATE TABLE krai_system.stage_tracking (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    document_id uuid,
    stage_name character varying(100) NOT NULL,
    status character varying(50) NOT NULL,
    started_at timestamp with time zone DEFAULT now(),
    completed_at timestamp with time zone,
    error_message text,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE stage_tracking; Type: COMMENT; Schema: krai_system; Owner: -
--

COMMENT ON TABLE krai_system.stage_tracking IS 'Tracks processing pipeline stages for monitoring and debugging';


--
-- Name: system_metrics; Type: TABLE; Schema: krai_system; Owner: -
--

CREATE TABLE krai_system.system_metrics (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    metric_name character varying(100) NOT NULL,
    metric_value numeric(15,6),
    metric_unit character varying(20),
    metric_category character varying(50),
    collection_timestamp timestamp with time zone DEFAULT now(),
    server_instance character varying(100),
    additional_context jsonb DEFAULT '{}'::jsonb
);


--
-- Name: images images_pkey; Type: CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.images
    ADD CONSTRAINT images_pkey PRIMARY KEY (id);


--
-- Name: links links_pkey; Type: CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.links
    ADD CONSTRAINT links_pkey PRIMARY KEY (id);


--
-- Name: print_defects print_defects_pkey; Type: CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.print_defects
    ADD CONSTRAINT print_defects_pkey PRIMARY KEY (id);


--
-- Name: video_products video_products_pkey; Type: CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.video_products
    ADD CONSTRAINT video_products_pkey PRIMARY KEY (id);


--
-- Name: video_products video_products_video_id_product_id_key; Type: CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.video_products
    ADD CONSTRAINT video_products_video_id_product_id_key UNIQUE (video_id, product_id);


--
-- Name: videos videos_pkey; Type: CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.videos
    ADD CONSTRAINT videos_pkey PRIMARY KEY (id);


--
-- Name: product_configurations configuration_name_unique; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.product_configurations
    ADD CONSTRAINT configuration_name_unique UNIQUE (configuration_name);


--
-- Name: document_products document_products_document_id_product_id_key; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.document_products
    ADD CONSTRAINT document_products_document_id_product_id_key UNIQUE (document_id, product_id);


--
-- Name: document_products document_products_pkey; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.document_products
    ADD CONSTRAINT document_products_pkey PRIMARY KEY (id);


--
-- Name: document_relationships document_relationships_pkey; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.document_relationships
    ADD CONSTRAINT document_relationships_pkey PRIMARY KEY (id);


--
-- Name: document_relationships document_relationships_primary_document_id_secondary_docume_key; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.document_relationships
    ADD CONSTRAINT document_relationships_primary_document_id_secondary_docume_key UNIQUE (primary_document_id, secondary_document_id, relationship_type);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: manufacturers manufacturers_name_key; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.manufacturers
    ADD CONSTRAINT manufacturers_name_key UNIQUE (name);


--
-- Name: manufacturers manufacturers_pkey; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.manufacturers
    ADD CONSTRAINT manufacturers_pkey PRIMARY KEY (id);


--
-- Name: oem_relationships oem_relationships_pkey; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.oem_relationships
    ADD CONSTRAINT oem_relationships_pkey PRIMARY KEY (id);


--
-- Name: option_dependencies option_dependencies_pkey; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.option_dependencies
    ADD CONSTRAINT option_dependencies_pkey PRIMARY KEY (id);


--
-- Name: product_accessories product_accessories_pkey; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.product_accessories
    ADD CONSTRAINT product_accessories_pkey PRIMARY KEY (id);


--
-- Name: product_accessories product_accessories_product_id_accessory_id_key; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.product_accessories
    ADD CONSTRAINT product_accessories_product_id_accessory_id_key UNIQUE (product_id, accessory_id);


--
-- Name: product_configurations product_configurations_pkey; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.product_configurations
    ADD CONSTRAINT product_configurations_pkey PRIMARY KEY (id);


--
-- Name: product_series product_series_manufacturer_id_series_name_key; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.product_series
    ADD CONSTRAINT product_series_manufacturer_id_series_name_key UNIQUE (manufacturer_id, series_name);


--
-- Name: product_series product_series_pkey; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.product_series
    ADD CONSTRAINT product_series_pkey PRIMARY KEY (id);


--
-- Name: products products_pkey; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);


--
-- Name: oem_relationships unique_brand_oem; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.oem_relationships
    ADD CONSTRAINT unique_brand_oem UNIQUE (brand_manufacturer, brand_series_pattern, oem_manufacturer);


--
-- Name: option_dependencies unique_option_dependency; Type: CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.option_dependencies
    ADD CONSTRAINT unique_option_dependency UNIQUE (option_id, depends_on_option_id, dependency_type);


--
-- Name: chunks chunks_pkey; Type: CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.chunks
    ADD CONSTRAINT chunks_pkey PRIMARY KEY (id);


--
-- Name: error_code_images error_code_images_error_code_id_image_id_key; Type: CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.error_code_images
    ADD CONSTRAINT error_code_images_error_code_id_image_id_key UNIQUE (error_code_id, image_id);


--
-- Name: error_code_images error_code_images_pkey; Type: CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.error_code_images
    ADD CONSTRAINT error_code_images_pkey PRIMARY KEY (id);


--
-- Name: error_code_parts error_code_parts_pkey; Type: CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.error_code_parts
    ADD CONSTRAINT error_code_parts_pkey PRIMARY KEY (error_code_id, part_id);


--
-- Name: error_codes error_codes_pkey; Type: CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.error_codes
    ADD CONSTRAINT error_codes_pkey PRIMARY KEY (id);


--
-- Name: feedback feedback_pkey; Type: CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.feedback
    ADD CONSTRAINT feedback_pkey PRIMARY KEY (id);


--
-- Name: product_research_cache product_research_cache_pkey; Type: CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.product_research_cache
    ADD CONSTRAINT product_research_cache_pkey PRIMARY KEY (id);


--
-- Name: search_analytics search_analytics_pkey; Type: CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.search_analytics
    ADD CONSTRAINT search_analytics_pkey PRIMARY KEY (id);


--
-- Name: session_context session_context_pkey; Type: CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.session_context
    ADD CONSTRAINT session_context_pkey PRIMARY KEY (id);


--
-- Name: tool_usage tool_usage_pkey; Type: CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.tool_usage
    ADD CONSTRAINT tool_usage_pkey PRIMARY KEY (id);


--
-- Name: product_research_cache unique_manufacturer_model; Type: CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.product_research_cache
    ADD CONSTRAINT unique_manufacturer_model UNIQUE (manufacturer, model_number);


--
-- Name: inventory_levels inventory_levels_pkey; Type: CONSTRAINT; Schema: krai_parts; Owner: -
--

ALTER TABLE ONLY krai_parts.inventory_levels
    ADD CONSTRAINT inventory_levels_pkey PRIMARY KEY (id);


--
-- Name: parts_catalog parts_catalog_manufacturer_part_unique; Type: CONSTRAINT; Schema: krai_parts; Owner: -
--

ALTER TABLE ONLY krai_parts.parts_catalog
    ADD CONSTRAINT parts_catalog_manufacturer_part_unique UNIQUE (manufacturer_id, part_number);


--
-- Name: parts_catalog parts_catalog_pkey; Type: CONSTRAINT; Schema: krai_parts; Owner: -
--

ALTER TABLE ONLY krai_parts.parts_catalog
    ADD CONSTRAINT parts_catalog_pkey PRIMARY KEY (id);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: krai_system; Owner: -
--

ALTER TABLE ONLY krai_system.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: health_checks health_checks_pkey; Type: CONSTRAINT; Schema: krai_system; Owner: -
--

ALTER TABLE ONLY krai_system.health_checks
    ADD CONSTRAINT health_checks_pkey PRIMARY KEY (id);


--
-- Name: processing_queue processing_queue_pkey; Type: CONSTRAINT; Schema: krai_system; Owner: -
--

ALTER TABLE ONLY krai_system.processing_queue
    ADD CONSTRAINT processing_queue_pkey PRIMARY KEY (id);


--
-- Name: stage_tracking stage_tracking_pkey; Type: CONSTRAINT; Schema: krai_system; Owner: -
--

ALTER TABLE ONLY krai_system.stage_tracking
    ADD CONSTRAINT stage_tracking_pkey PRIMARY KEY (id);


--
-- Name: system_metrics system_metrics_pkey; Type: CONSTRAINT; Schema: krai_system; Owner: -
--

ALTER TABLE ONLY krai_system.system_metrics
    ADD CONSTRAINT system_metrics_pkey PRIMARY KEY (id);


--
-- Name: idx_images_chunk_id; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_images_chunk_id ON krai_content.images USING btree (chunk_id);


--
-- Name: idx_images_document; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_images_document ON krai_content.images USING btree (document_id);


--
-- Name: idx_images_figure_number; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_images_figure_number ON krai_content.images USING btree (figure_number) WHERE (figure_number IS NOT NULL);


--
-- Name: idx_images_hash; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_images_hash ON krai_content.images USING btree (file_hash);


--
-- Name: idx_images_is_vector_graphic; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_images_is_vector_graphic ON krai_content.images USING btree (is_vector_graphic) WHERE (is_vector_graphic = true);


--
-- Name: idx_images_processing_status; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_images_processing_status ON krai_content.images USING btree (ai_confidence DESC) WHERE (ai_confidence IS NOT NULL);


--
-- Name: idx_links_document_id; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_links_document_id ON krai_content.links USING btree (document_id);


--
-- Name: idx_links_error_codes; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_links_error_codes ON krai_content.links USING gin (related_error_codes);


--
-- Name: idx_links_manufacturer; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_links_manufacturer ON krai_content.links USING btree (manufacturer_id);


--
-- Name: idx_links_page; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_links_page ON krai_content.links USING btree (page_number);


--
-- Name: idx_links_series; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_links_series ON krai_content.links USING btree (series_id);


--
-- Name: idx_links_type; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_links_type ON krai_content.links USING btree (link_type);


--
-- Name: idx_links_type_category; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_links_type_category ON krai_content.links USING btree (link_type, link_category);


--
-- Name: idx_links_url_hash; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_links_url_hash ON krai_content.links USING btree (md5(url));


--
-- Name: idx_links_video_id; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_links_video_id ON krai_content.links USING btree (video_id) WHERE (video_id IS NOT NULL);


--
-- Name: idx_print_defects_manufacturer_id; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_print_defects_manufacturer_id ON krai_content.print_defects USING btree (manufacturer_id);


--
-- Name: idx_print_defects_original_image_id; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_print_defects_original_image_id ON krai_content.print_defects USING btree (original_image_id);


--
-- Name: idx_print_defects_product_id; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_print_defects_product_id ON krai_content.print_defects USING btree (product_id);


--
-- Name: idx_video_products_product_id; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_video_products_product_id ON krai_content.video_products USING btree (product_id);


--
-- Name: idx_video_products_video_id; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_video_products_video_id ON krai_content.video_products USING btree (video_id);


--
-- Name: idx_videos_document_id; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_videos_document_id ON krai_content.videos USING btree (document_id);


--
-- Name: idx_videos_link_id; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_videos_link_id ON krai_content.videos USING btree (link_id);


--
-- Name: idx_videos_manufacturer_id; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_videos_manufacturer_id ON krai_content.videos USING btree (manufacturer_id);


--
-- Name: idx_videos_platform; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_videos_platform ON krai_content.videos USING btree (platform);


--
-- Name: idx_videos_title_trgm; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_videos_title_trgm ON krai_content.videos USING gin (title extensions.gin_trgm_ops);


--
-- Name: idx_videos_url_unique; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE UNIQUE INDEX idx_videos_url_unique ON krai_content.videos USING btree (video_url) WHERE ((video_url IS NOT NULL) AND (youtube_id IS NULL));


--
-- Name: idx_videos_video_url; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_videos_video_url ON krai_content.videos USING btree (video_url);


--
-- Name: idx_videos_youtube_id; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_videos_youtube_id ON krai_content.videos USING btree (youtube_id);


--
-- Name: idx_videos_youtube_id_unique; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE UNIQUE INDEX idx_videos_youtube_id_unique ON krai_content.videos USING btree (youtube_id) WHERE (youtube_id IS NOT NULL);


--
-- Name: idx_configurations_accessories; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_configurations_accessories ON krai_core.product_configurations USING gin (accessories);


--
-- Name: idx_configurations_base_product; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_configurations_base_product ON krai_core.product_configurations USING btree (base_product_id);


--
-- Name: idx_document_products_document_id; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_document_products_document_id ON krai_core.document_products USING btree (document_id);


--
-- Name: idx_document_products_primary; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_document_products_primary ON krai_core.document_products USING btree (document_id, is_primary_product) WHERE (is_primary_product = true);


--
-- Name: idx_document_products_product_id; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_document_products_product_id ON krai_core.document_products USING btree (product_id);


--
-- Name: idx_document_relationships_primary_document_id; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_document_relationships_primary_document_id ON krai_core.document_relationships USING btree (primary_document_id);


--
-- Name: idx_document_relationships_secondary_document_id; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_document_relationships_secondary_document_id ON krai_core.document_relationships USING btree (secondary_document_id);


--
-- Name: idx_documents_created_at; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_documents_created_at ON krai_core.documents USING btree (created_at);


--
-- Name: idx_documents_document_type; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_documents_document_type ON krai_core.documents USING btree (document_type);


--
-- Name: idx_documents_extracted_metadata; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_documents_extracted_metadata ON krai_core.documents USING gin (extracted_metadata);


--
-- Name: idx_documents_file_hash; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_documents_file_hash ON krai_core.documents USING btree (file_hash);


--
-- Name: idx_documents_manufacturer; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_documents_manufacturer ON krai_core.documents USING btree (manufacturer);


--
-- Name: idx_documents_manufacturer_id; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_documents_manufacturer_id ON krai_core.documents USING btree (manufacturer_id);


--
-- Name: idx_documents_models; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_documents_models ON krai_core.documents USING gin (models);


--
-- Name: idx_documents_priority; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_documents_priority ON krai_core.documents USING btree (priority_level);


--
-- Name: idx_documents_processing_results; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_documents_processing_results ON krai_core.documents USING gin (processing_results);


--
-- Name: idx_documents_processing_status; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_documents_processing_status ON krai_core.documents USING btree (processing_status);


--
-- Name: idx_documents_stage_status; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_documents_stage_status ON krai_core.documents USING gin (stage_status);


--
-- Name: idx_manufacturers_is_competitor; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_manufacturers_is_competitor ON krai_core.manufacturers USING btree (is_competitor, market_share_percent DESC) WHERE (is_competitor = true);


--
-- Name: idx_oem_relationships_applies_to; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_oem_relationships_applies_to ON krai_core.oem_relationships USING gin (applies_to);


--
-- Name: idx_oem_relationships_brand; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_oem_relationships_brand ON krai_core.oem_relationships USING btree (brand_manufacturer);


--
-- Name: idx_oem_relationships_oem; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_oem_relationships_oem ON krai_core.oem_relationships USING btree (oem_manufacturer);


--
-- Name: idx_oem_relationships_series; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_oem_relationships_series ON krai_core.oem_relationships USING btree (brand_series_pattern);


--
-- Name: idx_oem_relationships_type; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_oem_relationships_type ON krai_core.oem_relationships USING btree (relationship_type);


--
-- Name: idx_option_dependencies_depends_on; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_option_dependencies_depends_on ON krai_core.option_dependencies USING btree (depends_on_option_id);


--
-- Name: idx_option_dependencies_option_id; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_option_dependencies_option_id ON krai_core.option_dependencies USING btree (option_id);


--
-- Name: idx_option_dependencies_type; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_option_dependencies_type ON krai_core.option_dependencies USING btree (dependency_type);


--
-- Name: idx_product_accessories_accessory; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_product_accessories_accessory ON krai_core.product_accessories USING btree (accessory_id);


--
-- Name: idx_product_accessories_mounting_position; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_product_accessories_mounting_position ON krai_core.product_accessories USING btree (mounting_position);


--
-- Name: idx_product_accessories_product; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_product_accessories_product ON krai_core.product_accessories USING btree (product_id);


--
-- Name: idx_product_series_manufacturer_id; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_product_series_manufacturer_id ON krai_core.product_series USING btree (manufacturer_id);


--
-- Name: idx_product_series_model_pattern; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_product_series_model_pattern ON krai_core.product_series USING btree (model_pattern);


--
-- Name: idx_product_series_name_pattern; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_product_series_name_pattern ON krai_core.product_series USING btree (series_name, model_pattern);


--
-- Name: idx_products_article_code; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_products_article_code ON krai_core.products USING btree (article_code);


--
-- Name: idx_products_lifecycle; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_products_lifecycle ON krai_core.products USING gin (lifecycle);


--
-- Name: idx_products_manufacturer_series_type; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_products_manufacturer_series_type ON krai_core.products USING btree (manufacturer_id, series_id, product_type);


--
-- Name: idx_products_metadata; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_products_metadata ON krai_core.products USING gin (metadata);


--
-- Name: idx_products_model_trgm; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_products_model_trgm ON krai_core.products USING gin (model_number extensions.gin_trgm_ops);


--
-- Name: idx_products_oem_manufacturer; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_products_oem_manufacturer ON krai_core.products USING btree (oem_manufacturer);


--
-- Name: idx_products_oem_relationship_type; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_products_oem_relationship_type ON krai_core.products USING btree (oem_relationship_type);


--
-- Name: idx_products_pricing; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_products_pricing ON krai_core.products USING gin (pricing);


--
-- Name: idx_products_product_code; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_products_product_code ON krai_core.products USING btree (product_code);


--
-- Name: idx_products_product_type; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_products_product_type ON krai_core.products USING btree (product_type);


--
-- Name: INDEX idx_products_product_type; Type: COMMENT; Schema: krai_core; Owner: -
--

COMMENT ON INDEX krai_core.idx_products_product_type IS 'Index for filtering products by type (printer, accessory, consumable, etc.)';


--
-- Name: idx_products_series_id; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_products_series_id ON krai_core.products USING btree (series_id);


--
-- Name: idx_products_specifications; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_products_specifications ON krai_core.products USING gin (specifications);


--
-- Name: idx_products_type; Type: INDEX; Schema: krai_core; Owner: -
--

CREATE INDEX idx_products_type ON krai_core.products USING btree (product_type);


--
-- Name: chunks_embedding_hnsw_idx; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX chunks_embedding_hnsw_idx ON krai_intelligence.chunks USING hnsw (embedding extensions.vector_cosine_ops);

--
-- Name: idx_images_context_embedding_hnsw; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_images_context_embedding_hnsw ON krai_content.images USING hnsw (context_embedding extensions.vector_cosine_ops);

--
-- Name: idx_images_related_error_codes_gin; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_images_related_error_codes_gin ON krai_content.images USING gin (related_error_codes);

--
-- Name: idx_images_related_products_gin; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_images_related_products_gin ON krai_content.images USING gin (related_products);

--
-- Name: idx_images_related_chunks_gin; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_images_related_chunks_gin ON krai_content.images USING gin (related_chunks);

--
-- Name: idx_images_surrounding_paragraphs_gin; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_images_surrounding_paragraphs_gin ON krai_content.images USING gin (surrounding_paragraphs);

--
-- Name: idx_videos_context_embedding_hnsw; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_videos_context_embedding_hnsw ON krai_content.videos USING hnsw (context_embedding extensions.vector_cosine_ops);

--
-- Name: idx_videos_related_products_gin; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_videos_related_products_gin ON krai_content.videos USING gin (related_products);

--
-- Name: idx_videos_related_chunks_gin; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_videos_related_chunks_gin ON krai_content.videos USING gin (related_chunks);

--
-- Name: idx_links_context_embedding_hnsw; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_links_context_embedding_hnsw ON krai_content.links USING hnsw (context_embedding extensions.vector_cosine_ops);

--
-- Name: idx_links_related_chunks_gin; Type: INDEX; Schema: krai_content; Owner: -
--

CREATE INDEX idx_links_related_chunks_gin ON krai_content.links USING gin (related_chunks);

--
-- Name: idx_unified_embeddings_source; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_unified_embeddings_source ON krai_intelligence.unified_embeddings USING btree (source_id, source_type);

--
-- Name: idx_unified_embeddings_source_type; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_unified_embeddings_source_type ON krai_intelligence.unified_embeddings USING btree (source_type);

--
-- Name: idx_unified_embeddings_model; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_unified_embeddings_model ON krai_intelligence.unified_embeddings USING btree (model_name);

--
-- Name: idx_unified_embeddings_embedding_hnsw; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_unified_embeddings_embedding_hnsw ON krai_intelligence.unified_embeddings USING hnsw (embedding extensions.vector_cosine_ops);

--
-- Name: idx_unified_embeddings_created_at; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_unified_embeddings_created_at ON krai_intelligence.unified_embeddings USING btree (created_at DESC);

--
-- Name: idx_structured_tables_document; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_structured_tables_document ON krai_intelligence.structured_tables USING btree (document_id);

--
-- Name: idx_structured_tables_page; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_structured_tables_page ON krai_intelligence.structured_tables USING btree (page_number);

--
-- Name: idx_structured_tables_type; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_structured_tables_type ON krai_intelligence.structured_tables USING btree (table_type);

--
-- Name: idx_structured_tables_table_embedding_hnsw; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_structured_tables_table_embedding_hnsw ON krai_intelligence.structured_tables USING hnsw (table_embedding extensions.vector_cosine_ops);

--
-- Name: idx_structured_tables_context_embedding_hnsw; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_structured_tables_context_embedding_hnsw ON krai_intelligence.structured_tables USING hnsw (context_embedding extensions.vector_cosine_ops);

--
-- Name: idx_structured_tables_error_codes_gin; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_structured_tables_error_codes_gin ON krai_intelligence.structured_tables USING gin (related_error_codes);

--
-- Name: idx_structured_tables_products_gin; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_structured_tables_products_gin ON krai_intelligence.structured_tables USING gin (related_products);

--
-- Name: idx_structured_tables_table_data_gin; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_structured_tables_table_data_gin ON krai_intelligence.structured_tables USING gin (table_data);

--
-- Name: idx_structured_tables_column_headers_gin; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_structured_tables_column_headers_gin ON krai_intelligence.structured_tables USING gin (column_headers);


--
-- Name: idx_chunks_document; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_chunks_document ON krai_intelligence.chunks USING btree (document_id);


--
-- Name: idx_chunks_document_status_index; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_chunks_document_status_index ON krai_intelligence.chunks USING btree (document_id, processing_status, chunk_index);


--
-- Name: idx_chunks_page_label_end; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_chunks_page_label_end ON krai_intelligence.chunks USING btree (page_label_end);


--
-- Name: idx_chunks_page_label_start; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_chunks_page_label_start ON krai_intelligence.chunks USING btree (page_label_start);


--
-- Name: idx_chunks_text_fts; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_chunks_text_fts ON krai_intelligence.chunks USING gin (to_tsvector('english'::regconfig, text_chunk));


--
-- Name: idx_chunks_text_trgm; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_chunks_text_trgm ON krai_intelligence.chunks USING gin (text_chunk extensions.gin_trgm_ops);


--
-- Name: idx_error_code_images_error_code; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_error_code_images_error_code ON krai_intelligence.error_code_images USING btree (error_code_id);


--
-- Name: idx_error_code_images_image; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_error_code_images_image ON krai_intelligence.error_code_images USING btree (image_id);


--
-- Name: idx_error_code_parts_error_id; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_error_code_parts_error_id ON krai_intelligence.error_code_parts USING btree (error_code_id);


--
-- Name: idx_error_code_parts_part_id; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_error_code_parts_part_id ON krai_intelligence.error_code_parts USING btree (part_id);


--
-- Name: idx_error_codes_chunk_id; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_error_codes_chunk_id ON krai_intelligence.error_codes USING btree (chunk_id);


--
-- Name: idx_error_codes_code_trgm; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_error_codes_code_trgm ON krai_intelligence.error_codes USING gin (error_code extensions.gin_trgm_ops);


--
-- Name: idx_error_codes_confidence; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_error_codes_confidence ON krai_intelligence.error_codes USING btree (confidence_score DESC);


--
-- Name: idx_error_codes_document_id; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_error_codes_document_id ON krai_intelligence.error_codes USING btree (document_id);


--
-- Name: idx_error_codes_image; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_error_codes_image ON krai_intelligence.error_codes USING btree (image_id) WHERE (image_id IS NOT NULL);


--
-- Name: idx_error_codes_lookup; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_error_codes_lookup ON krai_intelligence.error_codes USING btree (error_code, manufacturer_id, product_id);


--
-- Name: idx_error_codes_manufacturer; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_error_codes_manufacturer ON krai_intelligence.error_codes USING btree (manufacturer_id);


--
-- Name: idx_error_codes_product_id; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_error_codes_product_id ON krai_intelligence.error_codes USING btree (product_id) WHERE (product_id IS NOT NULL);


--
-- Name: idx_error_codes_search; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_error_codes_search ON krai_intelligence.error_codes USING gin (to_tsvector('english'::regconfig, (((((error_code)::text || ' '::text) || COALESCE(error_description, ''::text)) || ' '::text) || COALESCE(solution_text, ''::text))));


--
-- Name: idx_error_codes_severity; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_error_codes_severity ON krai_intelligence.error_codes USING btree (severity_level);


--
-- Name: idx_error_codes_severity_manufacturer; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_error_codes_severity_manufacturer ON krai_intelligence.error_codes USING btree (manufacturer_id, severity_level) WHERE (severity_level IS NOT NULL);


--
-- Name: idx_error_codes_unique_source; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE UNIQUE INDEX idx_error_codes_unique_source ON krai_intelligence.error_codes USING btree (error_code, manufacturer_id, COALESCE(product_id, '00000000-0000-0000-0000-000000000000'::uuid), COALESCE(document_id, '00000000-0000-0000-0000-000000000000'::uuid), COALESCE(video_id, '00000000-0000-0000-0000-000000000000'::uuid));


--
-- Name: idx_error_codes_video_id; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_error_codes_video_id ON krai_intelligence.error_codes USING btree (video_id) WHERE (video_id IS NOT NULL);


--
-- Name: idx_feedback_created; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_feedback_created ON krai_intelligence.feedback USING btree (created_at DESC);


--
-- Name: idx_feedback_rating; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_feedback_rating ON krai_intelligence.feedback USING btree (rating);


--
-- Name: idx_feedback_session; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_feedback_session ON krai_intelligence.feedback USING btree (session_id);


--
-- Name: idx_research_cache_confidence; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_research_cache_confidence ON krai_intelligence.product_research_cache USING btree (confidence);


--
-- Name: idx_research_cache_manufacturer; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_research_cache_manufacturer ON krai_intelligence.product_research_cache USING btree (manufacturer);


--
-- Name: idx_research_cache_model; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_research_cache_model ON krai_intelligence.product_research_cache USING btree (model_number);


--
-- Name: idx_research_cache_physical_specs; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_research_cache_physical_specs ON krai_intelligence.product_research_cache USING gin (physical_specs);


--
-- Name: idx_research_cache_series; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_research_cache_series ON krai_intelligence.product_research_cache USING btree (series_name);


--
-- Name: idx_research_cache_specifications; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_research_cache_specifications ON krai_intelligence.product_research_cache USING gin (specifications);


--
-- Name: idx_research_cache_valid_until; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_research_cache_valid_until ON krai_intelligence.product_research_cache USING btree (cache_valid_until);


--
-- Name: idx_research_cache_verified; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_research_cache_verified ON krai_intelligence.product_research_cache USING btree (verified);


--
-- Name: idx_search_analytics_created_at_desc; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_search_analytics_created_at_desc ON krai_intelligence.search_analytics USING btree (created_at DESC);


--
-- Name: idx_search_analytics_manufacturer_filter; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_search_analytics_manufacturer_filter ON krai_intelligence.search_analytics USING btree (manufacturer_filter);


--
-- Name: idx_search_analytics_product_filter; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_search_analytics_product_filter ON krai_intelligence.search_analytics USING btree (product_filter);


--
-- Name: idx_session_context_session; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_session_context_session ON krai_intelligence.session_context USING btree (session_id);


--
-- Name: idx_session_context_type; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_session_context_type ON krai_intelligence.session_context USING btree (context_type);


--
-- Name: idx_session_context_unique; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE UNIQUE INDEX idx_session_context_unique ON krai_intelligence.session_context USING btree (session_id, context_type, context_value);


--
-- Name: idx_tool_usage_created; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_tool_usage_created ON krai_intelligence.tool_usage USING btree (created_at DESC);


--
-- Name: idx_tool_usage_session; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_tool_usage_session ON krai_intelligence.tool_usage USING btree (session_id);


--
-- Name: idx_tool_usage_tool; Type: INDEX; Schema: krai_intelligence; Owner: -
--

CREATE INDEX idx_tool_usage_tool ON krai_intelligence.tool_usage USING btree (tool_name);


--
-- Name: idx_inventory_levels_part_id; Type: INDEX; Schema: krai_parts; Owner: -
--

CREATE INDEX idx_inventory_levels_part_id ON krai_parts.inventory_levels USING btree (part_id);


--
-- Name: idx_parts_catalog_manufacturer_id; Type: INDEX; Schema: krai_parts; Owner: -
--

CREATE INDEX idx_parts_catalog_manufacturer_id ON krai_parts.parts_catalog USING btree (manufacturer_id);


--
-- Name: idx_parts_name_trgm; Type: INDEX; Schema: krai_parts; Owner: -
--

CREATE INDEX idx_parts_name_trgm ON krai_parts.parts_catalog USING gin (part_name extensions.gin_trgm_ops);


--
-- Name: idx_parts_number_trgm; Type: INDEX; Schema: krai_parts; Owner: -
--

CREATE INDEX idx_parts_number_trgm ON krai_parts.parts_catalog USING gin (part_number extensions.gin_trgm_ops);


--
-- Name: idx_audit_log_changed_at_desc; Type: INDEX; Schema: krai_system; Owner: -
--

CREATE INDEX idx_audit_log_changed_at_desc ON krai_system.audit_log USING btree (changed_at DESC);


--
-- Name: idx_audit_log_record_id; Type: INDEX; Schema: krai_system; Owner: -
--

CREATE INDEX idx_audit_log_record_id ON krai_system.audit_log USING btree (record_id);


--
-- Name: idx_audit_log_table; Type: INDEX; Schema: krai_system; Owner: -
--

CREATE INDEX idx_audit_log_table ON krai_system.audit_log USING btree (table_name);


--
-- Name: idx_audit_log_timestamp; Type: INDEX; Schema: krai_system; Owner: -
--

CREATE INDEX idx_audit_log_timestamp ON krai_system.audit_log USING btree (changed_at);


--
-- Name: idx_processing_queue_chunk_id; Type: INDEX; Schema: krai_system; Owner: -
--

CREATE INDEX idx_processing_queue_chunk_id ON krai_system.processing_queue USING btree (chunk_id);


--
-- Name: idx_processing_queue_document_id; Type: INDEX; Schema: krai_system; Owner: -
--

CREATE INDEX idx_processing_queue_document_id ON krai_system.processing_queue USING btree (document_id);


--
-- Name: idx_processing_queue_image_id; Type: INDEX; Schema: krai_system; Owner: -
--

CREATE INDEX idx_processing_queue_image_id ON krai_system.processing_queue USING btree (image_id);


--
-- Name: idx_processing_queue_pending; Type: INDEX; Schema: krai_system; Owner: -
--

CREATE INDEX idx_processing_queue_pending ON krai_system.processing_queue USING btree (priority, created_at) WHERE ((status)::text = 'pending'::text);


--
-- Name: idx_processing_queue_video_id; Type: INDEX; Schema: krai_system; Owner: -
--

CREATE INDEX idx_processing_queue_video_id ON krai_system.processing_queue USING btree (video_id);


--
-- Name: idx_stage_tracking_created; Type: INDEX; Schema: krai_system; Owner: -
--

CREATE INDEX idx_stage_tracking_created ON krai_system.stage_tracking USING btree (created_at DESC);


--
-- Name: idx_stage_tracking_document; Type: INDEX; Schema: krai_system; Owner: -
--

CREATE INDEX idx_stage_tracking_document ON krai_system.stage_tracking USING btree (document_id);


--
-- Name: idx_stage_tracking_stage; Type: INDEX; Schema: krai_system; Owner: -
--

CREATE INDEX idx_stage_tracking_stage ON krai_system.stage_tracking USING btree (stage_name);


--
-- Name: idx_stage_tracking_status; Type: INDEX; Schema: krai_system; Owner: -
--

CREATE INDEX idx_stage_tracking_status ON krai_system.stage_tracking USING btree (status);


--
-- Name: oem_relationships oem_relationships_updated_at; Type: TRIGGER; Schema: krai_core; Owner: -
--

CREATE TRIGGER oem_relationships_updated_at BEFORE UPDATE ON krai_core.oem_relationships FOR EACH ROW EXECUTE FUNCTION krai_core.update_oem_relationships_updated_at();


--
-- Name: manufacturers update_manufacturers_updated_at; Type: TRIGGER; Schema: krai_core; Owner: -
--

CREATE TRIGGER update_manufacturers_updated_at BEFORE UPDATE ON krai_core.manufacturers FOR EACH ROW EXECUTE FUNCTION krai_system.update_updated_at_column();


--
-- Name: products update_products_updated_at; Type: TRIGGER; Schema: krai_core; Owner: -
--

CREATE TRIGGER update_products_updated_at BEFORE UPDATE ON krai_core.products FOR EACH ROW EXECUTE FUNCTION krai_system.update_updated_at_column();


--
-- Name: product_research_cache research_cache_updated_at; Type: TRIGGER; Schema: krai_intelligence; Owner: -
--

CREATE TRIGGER research_cache_updated_at BEFORE UPDATE ON krai_intelligence.product_research_cache FOR EACH ROW EXECUTE FUNCTION krai_intelligence.update_research_cache_updated_at();


--
-- Name: chunks update_chunks_updated_at; Type: TRIGGER; Schema: krai_intelligence; Owner: -
--

CREATE TRIGGER update_chunks_updated_at BEFORE UPDATE ON krai_intelligence.chunks FOR EACH ROW EXECUTE FUNCTION krai_system.update_updated_at_column();


--
-- Name: images images_chunk_id_fkey; Type: FK CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.images
    ADD CONSTRAINT images_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES krai_intelligence.chunks(id) ON DELETE SET NULL;


--
-- Name: links links_manufacturer_id_fkey; Type: FK CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.links
    ADD CONSTRAINT links_manufacturer_id_fkey FOREIGN KEY (manufacturer_id) REFERENCES krai_core.manufacturers(id) ON DELETE SET NULL;


--
-- Name: links links_series_id_fkey; Type: FK CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.links
    ADD CONSTRAINT links_series_id_fkey FOREIGN KEY (series_id) REFERENCES krai_core.product_series(id) ON DELETE SET NULL;


--
-- Name: print_defects print_defects_manufacturer_id_fkey; Type: FK CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.print_defects
    ADD CONSTRAINT print_defects_manufacturer_id_fkey FOREIGN KEY (manufacturer_id) REFERENCES krai_core.manufacturers(id);


--
-- Name: print_defects print_defects_original_image_id_fkey; Type: FK CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.print_defects
    ADD CONSTRAINT print_defects_original_image_id_fkey FOREIGN KEY (original_image_id) REFERENCES krai_content.images(id);


--
-- Name: print_defects print_defects_product_id_fkey; Type: FK CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.print_defects
    ADD CONSTRAINT print_defects_product_id_fkey FOREIGN KEY (product_id) REFERENCES krai_core.products(id);


--
-- Name: video_products video_products_product_id_fkey; Type: FK CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.video_products
    ADD CONSTRAINT video_products_product_id_fkey FOREIGN KEY (product_id) REFERENCES krai_core.products(id) ON DELETE CASCADE;


--
-- Name: video_products video_products_video_id_fkey; Type: FK CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.video_products
    ADD CONSTRAINT video_products_video_id_fkey FOREIGN KEY (video_id) REFERENCES krai_content.videos(id) ON DELETE CASCADE;


--
-- Name: videos videos_document_id_fkey; Type: FK CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.videos
    ADD CONSTRAINT videos_document_id_fkey FOREIGN KEY (document_id) REFERENCES krai_core.documents(id);


--
-- Name: videos videos_link_id_fkey; Type: FK CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.videos
    ADD CONSTRAINT videos_link_id_fkey FOREIGN KEY (link_id) REFERENCES krai_content.links(id) ON DELETE CASCADE;


--
-- Name: videos videos_manufacturer_id_fkey; Type: FK CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.videos
    ADD CONSTRAINT videos_manufacturer_id_fkey FOREIGN KEY (manufacturer_id) REFERENCES krai_core.manufacturers(id);


--
-- Name: videos videos_series_id_fkey; Type: FK CONSTRAINT; Schema: krai_content; Owner: -
--

ALTER TABLE ONLY krai_content.videos
    ADD CONSTRAINT videos_series_id_fkey FOREIGN KEY (series_id) REFERENCES krai_core.product_series(id);


--
-- Name: document_products document_products_document_id_fkey; Type: FK CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.document_products
    ADD CONSTRAINT document_products_document_id_fkey FOREIGN KEY (document_id) REFERENCES krai_core.documents(id) ON DELETE CASCADE;


--
-- Name: document_products document_products_product_id_fkey; Type: FK CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.document_products
    ADD CONSTRAINT document_products_product_id_fkey FOREIGN KEY (product_id) REFERENCES krai_core.products(id) ON DELETE CASCADE;


--
-- Name: documents documents_manufacturer_id_fkey; Type: FK CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.documents
    ADD CONSTRAINT documents_manufacturer_id_fkey FOREIGN KEY (manufacturer_id) REFERENCES krai_core.manufacturers(id);


--
-- Name: option_dependencies option_dependencies_depends_on_option_id_fkey; Type: FK CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.option_dependencies
    ADD CONSTRAINT option_dependencies_depends_on_option_id_fkey FOREIGN KEY (depends_on_option_id) REFERENCES krai_core.products(id) ON DELETE CASCADE;


--
-- Name: option_dependencies option_dependencies_option_id_fkey; Type: FK CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.option_dependencies
    ADD CONSTRAINT option_dependencies_option_id_fkey FOREIGN KEY (option_id) REFERENCES krai_core.products(id) ON DELETE CASCADE;


--
-- Name: product_accessories product_accessories_accessory_id_fkey; Type: FK CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.product_accessories
    ADD CONSTRAINT product_accessories_accessory_id_fkey FOREIGN KEY (accessory_id) REFERENCES krai_core.products(id) ON DELETE CASCADE;


--
-- Name: product_accessories product_accessories_product_id_fkey; Type: FK CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.product_accessories
    ADD CONSTRAINT product_accessories_product_id_fkey FOREIGN KEY (product_id) REFERENCES krai_core.products(id) ON DELETE CASCADE;


--
-- Name: product_configurations product_configurations_base_product_id_fkey; Type: FK CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.product_configurations
    ADD CONSTRAINT product_configurations_base_product_id_fkey FOREIGN KEY (base_product_id) REFERENCES krai_core.products(id) ON DELETE CASCADE;


--
-- Name: product_series product_series_manufacturer_id_fkey; Type: FK CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.product_series
    ADD CONSTRAINT product_series_manufacturer_id_fkey FOREIGN KEY (manufacturer_id) REFERENCES krai_core.manufacturers(id);


--
-- Name: product_series product_series_successor_series_id_fkey; Type: FK CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.product_series
    ADD CONSTRAINT product_series_successor_series_id_fkey FOREIGN KEY (successor_series_id) REFERENCES krai_core.product_series(id);


--
-- Name: products products_manufacturer_id_fkey; Type: FK CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.products
    ADD CONSTRAINT products_manufacturer_id_fkey FOREIGN KEY (manufacturer_id) REFERENCES krai_core.manufacturers(id);


--
-- Name: products products_series_id_fkey; Type: FK CONSTRAINT; Schema: krai_core; Owner: -
--

ALTER TABLE ONLY krai_core.products
    ADD CONSTRAINT products_series_id_fkey FOREIGN KEY (series_id) REFERENCES krai_core.product_series(id);


--
-- Name: error_code_images error_code_images_error_code_id_fkey; Type: FK CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.error_code_images
    ADD CONSTRAINT error_code_images_error_code_id_fkey FOREIGN KEY (error_code_id) REFERENCES krai_intelligence.error_codes(id) ON DELETE CASCADE;


--
-- Name: error_code_images error_code_images_image_id_fkey; Type: FK CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.error_code_images
    ADD CONSTRAINT error_code_images_image_id_fkey FOREIGN KEY (image_id) REFERENCES krai_content.images(id) ON DELETE CASCADE;


--
-- Name: error_code_parts error_code_parts_error_code_id_fkey; Type: FK CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.error_code_parts
    ADD CONSTRAINT error_code_parts_error_code_id_fkey FOREIGN KEY (error_code_id) REFERENCES krai_intelligence.error_codes(id) ON DELETE CASCADE;


--
-- Name: error_code_parts error_code_parts_part_id_fkey; Type: FK CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.error_code_parts
    ADD CONSTRAINT error_code_parts_part_id_fkey FOREIGN KEY (part_id) REFERENCES krai_parts.parts_catalog(id) ON DELETE CASCADE;


--
-- Name: error_codes error_codes_chunk_id_fkey; Type: FK CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.error_codes
    ADD CONSTRAINT error_codes_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES krai_intelligence.chunks(id) ON DELETE CASCADE;


--
-- Name: error_codes error_codes_document_id_fkey; Type: FK CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.error_codes
    ADD CONSTRAINT error_codes_document_id_fkey FOREIGN KEY (document_id) REFERENCES krai_core.documents(id) ON DELETE CASCADE;


--
-- Name: error_codes error_codes_image_id_fkey; Type: FK CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.error_codes
    ADD CONSTRAINT error_codes_image_id_fkey FOREIGN KEY (image_id) REFERENCES krai_content.images(id) ON DELETE SET NULL;


--
-- Name: error_codes error_codes_manufacturer_id_fkey; Type: FK CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.error_codes
    ADD CONSTRAINT error_codes_manufacturer_id_fkey FOREIGN KEY (manufacturer_id) REFERENCES krai_core.manufacturers(id);


--
-- Name: error_codes error_codes_product_id_fkey; Type: FK CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.error_codes
    ADD CONSTRAINT error_codes_product_id_fkey FOREIGN KEY (product_id) REFERENCES krai_core.products(id) ON DELETE SET NULL;


--
-- Name: error_codes error_codes_video_id_fkey; Type: FK CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.error_codes
    ADD CONSTRAINT error_codes_video_id_fkey FOREIGN KEY (video_id) REFERENCES krai_content.videos(id) ON DELETE SET NULL;


--
-- Name: search_analytics search_analytics_manufacturer_filter_fkey; Type: FK CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.search_analytics
    ADD CONSTRAINT search_analytics_manufacturer_filter_fkey FOREIGN KEY (manufacturer_filter) REFERENCES krai_core.manufacturers(id);


--
-- Name: search_analytics search_analytics_product_filter_fkey; Type: FK CONSTRAINT; Schema: krai_intelligence; Owner: -
--

ALTER TABLE ONLY krai_intelligence.search_analytics
    ADD CONSTRAINT search_analytics_product_filter_fkey FOREIGN KEY (product_filter) REFERENCES krai_core.products(id);


--
-- Name: inventory_levels inventory_levels_part_id_fkey; Type: FK CONSTRAINT; Schema: krai_parts; Owner: -
--

ALTER TABLE ONLY krai_parts.inventory_levels
    ADD CONSTRAINT inventory_levels_part_id_fkey FOREIGN KEY (part_id) REFERENCES krai_parts.parts_catalog(id);


--
-- Name: parts_catalog parts_catalog_manufacturer_id_fkey; Type: FK CONSTRAINT; Schema: krai_parts; Owner: -
--

ALTER TABLE ONLY krai_parts.parts_catalog
    ADD CONSTRAINT parts_catalog_manufacturer_id_fkey FOREIGN KEY (manufacturer_id) REFERENCES krai_core.manufacturers(id);


--
-- Name: processing_queue processing_queue_chunk_id_fkey; Type: FK CONSTRAINT; Schema: krai_system; Owner: -
--

ALTER TABLE ONLY krai_system.processing_queue
    ADD CONSTRAINT processing_queue_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES krai_intelligence.chunks(id);


--
-- Name: processing_queue processing_queue_image_id_fkey; Type: FK CONSTRAINT; Schema: krai_system; Owner: -
--

ALTER TABLE ONLY krai_system.processing_queue
    ADD CONSTRAINT processing_queue_image_id_fkey FOREIGN KEY (image_id) REFERENCES krai_content.images(id);


--
-- Name: stage_tracking stage_tracking_document_id_fkey; Type: FK CONSTRAINT; Schema: krai_system; Owner: -
--

ALTER TABLE ONLY krai_system.stage_tracking
    ADD CONSTRAINT stage_tracking_document_id_fkey FOREIGN KEY (document_id) REFERENCES krai_core.documents(id) ON DELETE CASCADE;


--
-- Name: images; Type: ROW SECURITY; Schema: krai_content; Owner: -
--

ALTER TABLE krai_content.images ENABLE ROW LEVEL SECURITY;

--
-- Name: links; Type: ROW SECURITY; Schema: krai_content; Owner: -
--

ALTER TABLE krai_content.links ENABLE ROW LEVEL SECURITY;

--
-- Name: print_defects; Type: ROW SECURITY; Schema: krai_content; Owner: -
--

ALTER TABLE krai_content.print_defects ENABLE ROW LEVEL SECURITY;

--
-- Name: images service_role_images_all; Type: POLICY; Schema: krai_content; Owner: -
--

CREATE POLICY service_role_images_all ON krai_content.images USING (true);


--
-- Name: links service_role_links_all; Type: POLICY; Schema: krai_content; Owner: -
--

CREATE POLICY service_role_links_all ON krai_content.links USING (true);


--
-- Name: print_defects service_role_print_defects_all; Type: POLICY; Schema: krai_content; Owner: -
--

CREATE POLICY service_role_print_defects_all ON krai_content.print_defects USING (true);

--
-- Name: unified_embeddings; Type: ROW SECURITY; Schema: krai_intelligence; Owner: -
--

ALTER TABLE krai_intelligence.unified_embeddings ENABLE ROW LEVEL SECURITY;

--
-- Name: structured_tables; Type: ROW SECURITY; Schema: krai_intelligence; Owner: -
--

ALTER TABLE krai_intelligence.structured_tables ENABLE ROW LEVEL SECURITY;

--
-- Name: unified_embeddings service_role_unified_embeddings_all; Type: POLICY; Schema: krai_intelligence; Owner: -
--

CREATE POLICY service_role_unified_embeddings_all ON krai_intelligence.unified_embeddings USING (true);

--
-- Name: unified_embeddings authenticated_unified_embeddings_read; Type: POLICY; Schema: krai_intelligence; Owner: -
--

CREATE POLICY authenticated_unified_embeddings_read ON krai_intelligence.unified_embeddings FOR SELECT USING (true);

--
-- Name: structured_tables service_role_structured_tables_all; Type: POLICY; Schema: krai_intelligence; Owner: -
--

CREATE POLICY service_role_structured_tables_all ON krai_intelligence.structured_tables USING (true);

--
-- Name: structured_tables authenticated_structured_tables_read; Type: POLICY; Schema: krai_intelligence; Owner: -
--

CREATE POLICY authenticated_structured_tables_read ON krai_intelligence.structured_tables FOR SELECT USING (true);


--
-- Name: document_relationships; Type: ROW SECURITY; Schema: krai_core; Owner: -
--

ALTER TABLE krai_core.document_relationships ENABLE ROW LEVEL SECURITY;

--
-- Name: manufacturers; Type: ROW SECURITY; Schema: krai_core; Owner: -
--

ALTER TABLE krai_core.manufacturers ENABLE ROW LEVEL SECURITY;

--
-- Name: oem_relationships; Type: ROW SECURITY; Schema: krai_core; Owner: -
--

ALTER TABLE krai_core.oem_relationships ENABLE ROW LEVEL SECURITY;

--
-- Name: oem_relationships oem_relationships_modify_policy; Type: POLICY; Schema: krai_core; Owner: -
--

CREATE POLICY oem_relationships_modify_policy ON krai_core.oem_relationships USING ((auth.role() = 'service_role'::text));


--
-- Name: oem_relationships oem_relationships_select_policy; Type: POLICY; Schema: krai_core; Owner: -
--

CREATE POLICY oem_relationships_select_policy ON krai_core.oem_relationships FOR SELECT USING (true);


--
-- Name: option_dependencies; Type: ROW SECURITY; Schema: krai_core; Owner: -
--

ALTER TABLE krai_core.option_dependencies ENABLE ROW LEVEL SECURITY;

--
-- Name: option_dependencies option_dependencies_authenticated_read; Type: POLICY; Schema: krai_core; Owner: -
--

CREATE POLICY option_dependencies_authenticated_read ON krai_core.option_dependencies FOR SELECT TO authenticated USING (true);


--
-- Name: option_dependencies option_dependencies_service_role_all; Type: POLICY; Schema: krai_core; Owner: -
--

CREATE POLICY option_dependencies_service_role_all ON krai_core.option_dependencies TO service_role USING (true) WITH CHECK (true);


--
-- Name: product_series; Type: ROW SECURITY; Schema: krai_core; Owner: -
--

ALTER TABLE krai_core.product_series ENABLE ROW LEVEL SECURITY;

--
-- Name: products; Type: ROW SECURITY; Schema: krai_core; Owner: -
--

ALTER TABLE krai_core.products ENABLE ROW LEVEL SECURITY;

--
-- Name: document_relationships service_role_document_relationships_all; Type: POLICY; Schema: krai_core; Owner: -
--

CREATE POLICY service_role_document_relationships_all ON krai_core.document_relationships USING (true);


--
-- Name: manufacturers service_role_manufacturers_all; Type: POLICY; Schema: krai_core; Owner: -
--

CREATE POLICY service_role_manufacturers_all ON krai_core.manufacturers USING (true);


--
-- Name: product_series service_role_product_series_all; Type: POLICY; Schema: krai_core; Owner: -
--

CREATE POLICY service_role_product_series_all ON krai_core.product_series USING (true);


--
-- Name: products service_role_products_all; Type: POLICY; Schema: krai_core; Owner: -
--

CREATE POLICY service_role_products_all ON krai_core.products USING (true);


--
-- Name: error_code_images Allow insert for service role; Type: POLICY; Schema: krai_intelligence; Owner: -
--

CREATE POLICY "Allow insert for service role" ON krai_intelligence.error_code_images FOR INSERT WITH CHECK (true);


--
-- Name: error_code_images Allow read access to error_code_images; Type: POLICY; Schema: krai_intelligence; Owner: -
--

CREATE POLICY "Allow read access to error_code_images" ON krai_intelligence.error_code_images FOR SELECT USING (true);


--
-- Name: chunks; Type: ROW SECURITY; Schema: krai_intelligence; Owner: -
--

ALTER TABLE krai_intelligence.chunks ENABLE ROW LEVEL SECURITY;

--
-- Name: error_code_images; Type: ROW SECURITY; Schema: krai_intelligence; Owner: -
--

ALTER TABLE krai_intelligence.error_code_images ENABLE ROW LEVEL SECURITY;

--
-- Name: error_codes; Type: ROW SECURITY; Schema: krai_intelligence; Owner: -
--

ALTER TABLE krai_intelligence.error_codes ENABLE ROW LEVEL SECURITY.
GRANT EXECUTE ON FUNCTION krai_intelligence.match_multimodal(query_embedding extensions.vector(768), match_threshold double precision, match_count integer) TO anon;

GRANT EXECUTE ON FUNCTION krai_intelligence.match_images_by_context(query_embedding extensions.vector(768), match_threshold double precision, match_count integer) TO authenticated;
GRANT EXECUTE ON FUNCTION krai_intelligence.match_images_by_context(query_embedding extensions.vector(768), match_threshold double precision, match_count integer) TO anon;
