# KRAI Database Schema Documentation
================================================================================

**Zuletzt aktualisiert:** 20.05.2026 um 11:49 UTC

**Quelle:** Live PostgreSQL (`krai`) — **nicht** manuell gepflegt

**Schema-Fingerprint:** `98c8bb67f30dd682`

> Regenerieren: `python scripts/generate_schema_docs.py`
> Visuell: `schema/krai.dbml` → [dbdiagram.io](https://dbdiagram.io)

## ⚠️ WICHTIGE INFORMATIONEN

### Embeddings Storage
- Embeddings in `krai_intelligence.chunks` Spalte `embedding`
- Typ: `vector(768)`
- Kein separates krai_embeddings Schema. Embeddings nur in dieser Tabelle.

### View Naming Convention
- Views: `public.vw_*`
- Tabellen in `krai_*` Schemas
- Embeddings liegen in krai_intelligence.chunks.embedding — nicht in Views suchen.

### ⚠️ Known Column Name Traps

| FALSCH | RICHTIG | Tabelle | Beschreibung |
|--------|---------|---------|--------------|
| `chunk_text` | `text_chunk` | `krai_intelligence.chunks` | Text-Inhalt der Chunks |
| `enrichment_error` | `metadata->>'enrichment_error'` | `krai_content.videos` | Keine eigene Spalte — Wert liegt in JSONB metadata |
| `tags` | `metadata->>'tags'` | `krai_content.videos` | Keine eigene Spalte — Wert liegt in JSONB metadata |
| `solution_text` | `solution_technician_text` | `krai_intelligence.error_codes` | Seit Migration 025 in drei solution_* Spalten aufgeteilt |
| `requires_technician` | `(entfernt)` | `krai_intelligence.error_codes` | Spalte existiert nicht mehr |
| `Error-Code Großbuchstaben` | `error_code (Kleinbuchstaben)` | `krai_intelligence.error_codes` | error_code immer lowercase speichern/abfragen |

### 🔑 Wichtige Query-Muster

```sql
-- Chunks mit Embeddings
SELECT id, text_chunk, embedding FROM krai_intelligence.chunks
WHERE embedding IS NOT NULL LIMIT 10;

-- Videos mit Fehler (metadata JSONB)
SELECT id, title, metadata->>'enrichment_error' AS error
FROM krai_content.videos
WHERE metadata->>'enrichment_error' IS NOT NULL;

-- Error Code Hierarchy
SELECT error_code, error_description, parent_code, is_category
FROM krai_intelligence.error_codes
WHERE parent_code = '13.B9' ORDER BY error_code;
```

---

## Table of Contents

- [krai_content](#krai-content) (7 Tabellen/Views)
- [krai_core](#krai-core) (10 Tabellen/Views)
- [krai_intelligence](#krai-intelligence) (6 Tabellen/Views)
- [krai_parts](#krai-parts) (2 Tabellen/Views)
- [krai_pm](#krai-pm) (11 Tabellen/Views)
- [krai_system](#krai-system) (20 Tabellen/Views)
- [krai_users](#krai-users) (5 Tabellen/Views)
- [public](#public) (3 Tabellen/Views)

---

## krai_content

*Media — images, videos, links, print_defects*

### krai_content.document_media_context
> Unified view for agent context: documents with images, figures, and links

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `document_id` | uuid | YES | - |
| `filename` | varchar(255) | YES | - |
| `manufacturer` | varchar(100) | YES | - |
| `document_type` | varchar(100) | YES | - |
| `image_id` | uuid | YES | - |
| `image_filename` | varchar(255) | YES | - |
| `figure_number` | varchar(50) | YES | - |
| `figure_context` | text | YES | - |
| `image_page` | integer | YES | - |
| `image_url` | text | YES | - |
| `link_id` | uuid | YES | - |
| `link_url` | text | YES | - |
| `link_type` | varchar(50) | YES | - |
| `link_page` | integer | YES | - |
| `link_description` | text | YES | - |

### krai_content.images
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `document_id` | uuid | YES | - |
| `chunk_id` | uuid | YES | - |
| `filename` | varchar(255) | YES | - |
| `original_filename` | varchar(255) | YES | - |
| `storage_path` | text | YES | - |
| `storage_url` | text | NO | - |
| `file_size` | integer | YES | - |
| `image_format` | varchar(10) | YES | - |
| `width_px` | integer | YES | - |
| `height_px` | integer | YES | - |
| `page_number` | integer | YES | - |
| `image_index` | integer | YES | - |
| `image_type` | varchar(50) | YES | - |
| `ai_description` | text | YES | - |
| `ai_confidence` | numeric | YES | - |
| `contains_text` | boolean | YES | false |
| `ocr_text` | text | YES | - |
| `ocr_confidence` | numeric | YES | - |
| `manual_description` | text | YES | - |
| `tags` | _text | YES | - |
| `file_hash` | varchar(64) | YES | - |
| `figure_number` | varchar(50) | YES | - |
| `figure_context` | text | YES | - |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |
| `svg_storage_url` | text | YES | - |
| `original_svg_content` | text | YES | - |
| `is_vector_graphic` | boolean | YES | false |
| `has_png_derivative` | boolean | YES | true |
| `context_caption` | text | YES | - |
| `page_header` | text | YES | - |
| `surrounding_paragraphs` | _text | YES | - |
| `related_error_codes` | _text | YES | - |
| `related_products` | _text | YES | - |
| `related_chunks` | _uuid | YES | - |
| `context_embedding` | vector(768) | YES | - |
| `figure_reference` | text | YES | - |

**Foreign Keys:**
- `document_id` → `krai_core.documents.id`

### krai_content.instructional_videos
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `manufacturer_id` | uuid | NO | - |
| `title` | varchar(255) | NO | - |
| `description` | text | YES | - |
| `video_url` | text | NO | - |
| `thumbnail_url` | text | YES | - |
| `duration_seconds` | integer | YES | - |
| `file_size_mb` | integer | YES | - |
| `video_format` | varchar(20) | YES | - |
| `resolution` | varchar(20) | YES | - |
| `language` | varchar(10) | YES | 'en'::character varying |
| `created_at` | timestamp with time zone | YES | now() |

**Foreign Keys:**
- `manufacturer_id` → `krai_core.manufacturers.id`

### krai_content.links
> External links extracted from PDFs (videos, tutorials, etc.)

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `document_id` | uuid | NO | - |
| `url` | text | NO | - |
| `link_type` | varchar(50) | NO | 'external'::character varying |
| `page_number` | integer | NO | - |
| `description` | text | YES | - |
| `position_data` | jsonb | YES | - |
| `is_active` | boolean | YES | true |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |
| `metadata` | jsonb | YES | '{}'::jsonb |
| `link_category` | varchar(50) | YES | - |
| `confidence_score` | numeric | YES | 0.0 |
| `manufacturer_id` | uuid | YES | - |
| `series_id` | uuid | YES | - |
| `related_error_codes` | _text | YES | - |
| `context_description` | text | YES | - |
| `related_chunks` | _uuid | YES | - |
| `scraped_content` | text | YES | - |
| `scraped_metadata` | jsonb | YES | '{}'::jsonb |
| `scrape_status` | varchar(20) | YES | 'pending'::character varying |
| `content_hash` | varchar(64) | YES | - |
| `retry_count` | integer | YES | 0 |
| `last_scraped_at` | timestamp with time zone | YES | - |

**Foreign Keys:**
- `document_id` → `krai_core.documents.id`

### krai_content.print_defects
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `manufacturer_id` | uuid | NO | - |
| `product_id` | uuid | YES | - |
| `original_image_id` | uuid | YES | - |
| `defect_name` | varchar(100) | NO | - |
| `defect_category` | varchar(50) | YES | - |
| `defect_description` | text | YES | - |
| `example_image_url` | text | YES | - |
| `annotated_image_url` | text | YES | - |
| `detection_confidence` | numeric | YES | - |
| `common_causes` | jsonb | YES | '[]'::jsonb |
| `recommended_solutions` | jsonb | YES | '[]'::jsonb |
| `related_error_codes` | _text | YES | - |
| `created_at` | timestamp with time zone | YES | now() |

**Foreign Keys:**
- `product_id` → `krai_core.products.id`
- `original_image_id` → `krai_content.images.id`
- `manufacturer_id` → `krai_core.manufacturers.id`

### krai_content.video_products
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `video_id` | uuid | NO | - |
| `product_id` | uuid | NO | - |
| `created_at` | timestamp with time zone | YES | now() |

### krai_content.videos
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `link_id` | uuid | YES | - |
| `youtube_id` | varchar(20) | YES | - |
| `platform` | varchar(20) | YES | - |
| `video_url` | text | YES | - |
| `title` | varchar(500) | NO | 'Untitled'::character varying |
| `description` | text | YES | - |
| `thumbnail_url` | text | YES | - |
| `duration` | integer | YES | - |
| `channel_id` | varchar(50) | YES | - |
| `channel_title` | varchar(200) | YES | - |
| `published_at` | timestamp with time zone | YES | - |
| `manufacturer_id` | uuid | YES | - |
| `series_id` | uuid | YES | - |
| `document_id` | uuid | YES | - |
| `metadata` | jsonb | YES | - |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |
| `enriched_at` | timestamp with time zone | YES | now() |
| `context_description` | text | YES | - |
| `related_products` | _text | YES | - |
| `related_chunks` | _uuid | YES | - |
| `page_number` | integer | YES | - |
| `context_embedding` | vector(768) | YES | - |
| `product_id` | uuid | YES | - |

**Foreign Keys:**
- `product_id` → `krai_core.products.id`

## krai_core

*Business-Entitäten — documents, products, manufacturers, series*

### krai_core.document_products
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `document_id` | uuid | NO | - |
| `product_id` | uuid | NO | - |
| `relevance_score` | numeric | YES | - |
| `created_at` | timestamp with time zone | YES | now() |

**Foreign Keys:**
- `product_id` → `krai_core.products.id`
- `document_id` → `krai_core.documents.id`

### krai_core.document_relationships
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `primary_document_id` | uuid | NO | - |
| `secondary_document_id` | uuid | NO | - |
| `relationship_type` | varchar(50) | NO | - |
| `relationship_strength` | numeric | YES | 0.5 |
| `auto_discovered` | boolean | YES | true |
| `manual_verification` | boolean | YES | false |
| `verification_date` | timestamp with time zone | YES | - |
| `verified_by` | varchar(100) | YES | - |
| `notes` | text | YES | - |
| `created_at` | timestamp with time zone | YES | now() |

**Foreign Keys:**
- `primary_document_id` → `krai_core.documents.id`
- `secondary_document_id` → `krai_core.documents.id`

### krai_core.documents
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `manufacturer_id` | uuid | YES | - |
| `product_id` | uuid | YES | - |
| `filename` | varchar(255) | NO | - |
| `original_filename` | varchar(255) | YES | - |
| `file_size` | bigint | YES | - |
| `file_hash` | varchar(64) | YES | - |
| `storage_path` | text | YES | - |
| `storage_url` | text | YES | - |
| `document_type` | varchar(100) | YES | - |
| `language` | varchar(10) | YES | 'en'::character varying |
| `version` | varchar(50) | YES | - |
| `publish_date` | date | YES | - |
| `page_count` | integer | YES | - |
| `word_count` | integer | YES | - |
| `character_count` | integer | YES | - |
| `content_text` | text | YES | - |
| `content_summary` | text | YES | - |
| `extracted_metadata` | jsonb | YES | '{}'::jsonb |
| `processing_status` | varchar(50) | YES | 'pending'::character varying |
| `confidence_score` | numeric | YES | - |
| `manual_review_required` | boolean | YES | false |
| `manual_review_completed` | boolean | YES | false |
| `manual_review_notes` | text | YES | - |
| `ocr_confidence` | numeric | YES | - |
| `manufacturer` | varchar(100) | YES | - |
| `series` | varchar(100) | YES | - |
| `models` | _text | YES | - |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |
| `stage_status` | jsonb | NO | '{}'::jsonb |

**Foreign Keys:**
- `manufacturer_id` → `krai_core.manufacturers.id`
- `product_id` → `krai_core.products.id`

### krai_core.manufacturers
> Printer and office equipment manufacturers. Seeded with 14 major manufacturers on 2025-10-09.

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `name` | varchar(100) | NO | - |
| `short_name` | varchar(10) | YES | - |
| `country` | varchar(50) | YES | - |
| `founded_year` | integer | YES | - |
| `website` | varchar(255) | YES | - |
| `support_email` | varchar(255) | YES | - |
| `support_phone` | varchar(50) | YES | - |
| `logo_url` | text | YES | - |
| `is_competitor` | boolean | YES | false |
| `market_share_percent` | numeric | YES | - |
| `annual_revenue_usd` | bigint | YES | - |
| `employee_count` | integer | YES | - |
| `headquarters_address` | text | YES | - |
| `stock_symbol` | varchar(10) | YES | - |
| `primary_business_segment` | varchar(100) | YES | - |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

### krai_core.product_accessories
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `product_id` | uuid | NO | - |
| `accessory_id` | uuid | NO | - |
| `accessory_type` | varchar(50) | YES | - |
| `is_required` | boolean | YES | false |
| `created_at` | timestamp with time zone | YES | now() |

**Foreign Keys:**
- `product_id` → `krai_core.products.id`
- `accessory_id` → `krai_core.products.id`

### krai_core.product_series
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `manufacturer_id` | uuid | NO | - |
| `series_name` | varchar(100) | NO | - |
| `series_code` | varchar(50) | YES | - |
| `launch_date` | date | YES | - |
| `end_of_life_date` | date | YES | - |
| `target_market` | varchar(100) | YES | - |
| `price_range` | varchar(50) | YES | - |
| `key_features` | jsonb | YES | '{}'::jsonb |
| `series_description` | text | YES | - |
| `marketing_name` | varchar(150) | YES | - |
| `successor_series_id` | uuid | YES | - |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

**Foreign Keys:**
- `manufacturer_id` → `krai_core.manufacturers.id`
- `successor_series_id` → `krai_core.product_series.id`

### krai_core.products
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `parent_id` | uuid | YES | - |
| `manufacturer_id` | uuid | NO | - |
| `series_id` | uuid | YES | - |
| `model_number` | varchar(100) | NO | - |
| `model_name` | varchar(200) | YES | - |
| `product_type` | varchar(50) | NO | 'laser_printer'::character varying |
| `launch_date` | date | YES | - |
| `end_of_life_date` | date | YES | - |
| `msrp_usd` | numeric | YES | - |
| `weight_kg` | numeric | YES | - |
| `dimensions_mm` | jsonb | YES | - |
| `color_options` | _text | YES | - |
| `connectivity_options` | _text | YES | - |
| `print_technology` | varchar(50) | YES | - |
| `max_print_speed_ppm` | integer | YES | - |
| `max_resolution_dpi` | integer | YES | - |
| `max_paper_size` | varchar(20) | YES | - |
| `duplex_capable` | boolean | YES | false |
| `network_capable` | boolean | YES | false |
| `mobile_print_support` | boolean | YES | false |
| `supported_languages` | _text | YES | - |
| `energy_star_certified` | boolean | YES | false |
| `warranty_months` | integer | YES | 12 |
| `service_manual_url` | text | YES | - |
| `parts_catalog_url` | text | YES | - |
| `driver_download_url` | text | YES | - |
| `firmware_version` | varchar(50) | YES | - |
| `option_dependencies` | jsonb | YES | '{}'::jsonb |
| `replacement_parts` | jsonb | YES | '{}'::jsonb |
| `common_issues` | jsonb | YES | '{}'::jsonb |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |
| `specifications` | jsonb | YES | '{}'::jsonb |
| `pricing` | jsonb | YES | '{}'::jsonb |
| `lifecycle` | jsonb | YES | '{}'::jsonb |
| `urls` | jsonb | YES | '{}'::jsonb |
| `metadata` | jsonb | YES | '{}'::jsonb |
| `oem_manufacturer` | varchar(100) | YES | - |
| `oem_relationship_type` | varchar(50) | YES | - |
| `oem_notes` | text | YES | - |
| `article_code` | varchar(50) | YES | - |

**Foreign Keys:**
- `parent_id` → `krai_core.products.id`
- `series_id` → `krai_core.product_series.id`
- `manufacturer_id` → `krai_core.manufacturers.id`

### krai_core.public_products
> Public view of products with non-sensitive information only

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | YES | - |
| `manufacturer_id` | uuid | YES | - |
| `series_id` | uuid | YES | - |
| `model_number` | varchar(100) | YES | - |
| `model_name` | varchar(200) | YES | - |
| `product_type` | varchar(50) | YES | - |
| `launch_date` | date | YES | - |
| `print_technology` | varchar(50) | YES | - |
| `max_print_speed_ppm` | integer | YES | - |
| `max_resolution_dpi` | integer | YES | - |
| `created_at` | timestamp with time zone | YES | - |

### krai_core.vw_documents_by_stage
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | YES | - |
| `filename` | varchar(255) | YES | - |
| `processing_status` | varchar(50) | YES | - |
| `current_stage` | text | YES | - |
| `progress_percentage` | numeric | YES | - |
| `upload_status` | text | YES | - |
| `text_extraction_status` | text | YES | - |
| `image_processing_status` | text | YES | - |
| `classification_status` | text | YES | - |
| `metadata_extraction_status` | text | YES | - |
| `storage_status` | text | YES | - |
| `embedding_status` | text | YES | - |
| `search_indexing_status` | text | YES | - |
| `created_at` | timestamp with time zone | YES | - |
| `updated_at` | timestamp with time zone | YES | - |

### krai_core.vw_stage_statistics
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `stage_name` | text | YES | - |
| `pending_count` | bigint | YES | - |
| `processing_count` | bigint | YES | - |
| `completed_count` | bigint | YES | - |
| `failed_count` | bigint | YES | - |
| `skipped_count` | bigint | YES | - |
| `avg_duration_seconds` | numeric | YES | - |

## krai_intelligence

*AI/ML — chunks, embeddings, error_codes, solutions*

### krai_intelligence.chunks
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `document_id` | uuid | NO | - |
| `text_chunk` | text | NO | - |
| `chunk_index` | integer | NO | - |
| `page_start` | integer | YES | - |
| `page_end` | integer | YES | - |
| `processing_status` | varchar(20) | YES | 'pending'::character varying |
| `fingerprint` | varchar(32) | NO | - |
| `metadata` | jsonb | YES | '{}'::jsonb |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |
| `embedding` | vector(768) | YES | - |

**Foreign Keys:**
- `document_id` → `krai_core.documents.id`

### krai_intelligence.error_codes
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `chunk_id` | uuid | YES | - |
| `document_id` | uuid | YES | - |
| `manufacturer_id` | uuid | YES | - |
| `error_code` | varchar(20) | NO | - |
| `error_description` | text | YES | - |
| `page_number` | integer | YES | - |
| `confidence_score` | numeric | YES | - |
| `extraction_method` | varchar(50) | YES | - |
| `requires_parts` | boolean | YES | false |
| `estimated_fix_time_minutes` | integer | YES | - |
| `severity_level` | varchar(20) | YES | - |
| `created_at` | timestamp with time zone | YES | now() |
| `parent_code` | varchar(50) | YES | - |
| `is_category` | boolean | YES | false |
| `solution_customer_text` | text | YES | - |
| `solution_agent_text` | text | YES | - |
| `solution_technician_text` | text | YES | - |
| `product_ids` | _uuid | YES | '{}'::uuid[] |

**Foreign Keys:**
- `chunk_id` → `krai_intelligence.chunks.id`
- `document_id` → `krai_core.documents.id`
- `manufacturer_id` → `krai_core.manufacturers.id`

### krai_intelligence.manufacturer_verification_cache
> Cache for web-based manufacturer verification results from Firecrawl searches

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `verification_type` | varchar(50) | NO | - |
| `cache_key` | varchar(255) | NO | - |
| `manufacturer` | varchar(255) | YES | - |
| `model_number` | varchar(255) | YES | - |
| `verification_data` | jsonb | NO | - |
| `confidence` | double precision | YES | - |
| `source_url` | text | YES | - |
| `cached_at` | timestamp with time zone | YES | now() |
| `cache_valid_until` | timestamp with time zone | YES | - |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

### krai_intelligence.search_analytics
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `search_query` | text | NO | - |
| `search_type` | varchar(50) | YES | - |
| `results_count` | integer | YES | - |
| `click_through_rate` | numeric | YES | - |
| `user_satisfaction_rating` | integer | YES | - |
| `search_duration_ms` | integer | YES | - |
| `result_relevance_scores` | jsonb | YES | - |
| `user_session_id` | varchar(100) | YES | - |
| `user_id` | uuid | YES | - |
| `manufacturer_filter` | uuid | YES | - |
| `product_filter` | uuid | YES | - |
| `document_type_filter` | varchar(100) | YES | - |
| `language_filter` | varchar(10) | YES | - |
| `created_at` | timestamp with time zone | YES | now() |

**Foreign Keys:**
- `manufacturer_filter` → `krai_core.manufacturers.id`
- `product_filter` → `krai_core.products.id`

### krai_intelligence.structured_tables
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `document_id` | uuid | NO | - |
| `chunk_id` | uuid | YES | - |
| `page_number` | integer | YES | - |
| `table_index` | integer | YES | - |
| `table_data` | jsonb | NO | - |
| `table_markdown` | text | YES | - |
| `column_headers` | _text | YES | - |
| `row_count` | integer | YES | - |
| `column_count` | integer | YES | - |
| `table_embedding` | vector(768) | YES | - |
| `context_embedding` | vector(768) | YES | - |
| `column_embeddings` | jsonb | YES | - |
| `metadata` | jsonb | YES | '{}'::jsonb |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |
| `table_type` | varchar(50) | YES | - |
| `caption` | text | YES | - |
| `context_text` | text | YES | - |
| `bbox` | jsonb | YES | - |

**Foreign Keys:**
- `document_id` → `krai_core.documents.id`
- `chunk_id` → `krai_intelligence.chunks.id`

### krai_intelligence.unified_embeddings
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `source_id` | uuid | NO | - |
| `source_type` | varchar(20) | NO | - |
| `embedding` | vector(768) | NO | - |
| `model_name` | varchar(100) | NO | - |
| `embedding_context` | text | YES | - |
| `metadata` | jsonb | YES | '{}'::jsonb |
| `created_at` | timestamp with time zone | YES | now() |

## krai_parts

*Ersatzteile — parts_catalog, accessories*

### krai_parts.inventory_levels
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `part_id` | uuid | NO | - |
| `warehouse_location` | varchar(100) | YES | - |
| `current_stock` | integer | YES | 0 |
| `minimum_stock_level` | integer | YES | 0 |
| `maximum_stock_level` | integer | YES | 1000 |
| `last_updated` | timestamp with time zone | YES | now() |

**Foreign Keys:**
- `part_id` → `krai_parts.parts_catalog.id`

### krai_parts.parts_catalog
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `manufacturer_id` | uuid | NO | - |
| `part_number` | varchar(100) | NO | - |
| `part_name` | varchar(255) | YES | - |
| `part_description` | text | YES | - |
| `part_category` | varchar(100) | YES | - |
| `unit_price_usd` | numeric | YES | - |
| `created_at` | timestamp with time zone | YES | now() |
| `product_id` | uuid | YES | - |

**Foreign Keys:**
- `manufacturer_id` → `krai_core.manufacturers.id`

## krai_pm

*Project Management (eigenes Schema)*

### krai_pm.device_lifecycle
> Device counter readings and maintenance events from Docuform, pseudonymized.

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `device_serial_hash` | varchar(64) | NO | - |
| `product_id` | uuid | YES | - |
| `counter_total` | bigint | YES | - |
| `counter_color` | bigint | YES | - |
| `counter_bw` | bigint | YES | - |
| `measured_at` | timestamp with time zone | NO | - |
| `toner_levels` | jsonb | YES | - |
| `maintenance_events` | jsonb | YES | - |
| `metadata` | jsonb | YES | - |
| `ingested_at` | timestamp with time zone | YES | now() |
| `radix_device_id` | varchar(100) | YES | - |
| `radix_system_id` | varchar(100) | YES | - |

**Foreign Keys:**
- `product_id` → `krai_core.products.id`

### krai_pm.entity_mapping
> Pseudonymization mapping â€“ access restricted.

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `entity_type` | varchar(50) | NO | - |
| `raw_value` | text | NO | - |
| `hash_value` | varchar(64) | NO | - |
| `created_at` | timestamp with time zone | YES | now() |

### krai_pm.part_lifetimes
> OEM nominal lifetimes for consumables per manufacturer/product/part.

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `manufacturer_id` | uuid | NO | - |
| `product_id` | uuid | YES | - |
| `part_category` | varchar(50) | NO | - |
| `part_number` | varchar(100) | YES | - |
| `nominal_lifetime_pages` | integer | YES | - |
| `color_channel` | varchar(10) | YES | - |
| `source` | varchar(50) | NO | - |
| `metadata` | jsonb | YES | - |
| `ingested_at` | timestamp with time zone | YES | now() |
| `radix_part_id` | varchar(100) | YES | - |
| `part_number_variants` | _text | YES | - |
| `manufacturer_part_code` | varchar(100) | YES | - |

**Foreign Keys:**
- `product_id` → `krai_core.products.id`
- `manufacturer_id` → `krai_core.manufacturers.id`

### krai_pm.part_warranty_events
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | integer | NO | nextval('krai_pm.part_warranty_events_id_seq'::regclass) |
| `ticket_id` | varchar(255) | YES | - |
| `manufacturer_id` | uuid | YES | - |
| `part_category` | varchar(50) | NO | - |
| `part_number` | varchar(100) | YES | - |
| `failure_date` | timestamp without time zone | NO | - |
| `warranty_expiry_date` | timestamp without time zone | YES | - |
| `is_in_warranty` | boolean | YES | false |
| `nominal_lifetime_pages` | integer | YES | - |
| `actual_runtime_pages` | integer | YES | - |
| `mismatch_ratio` | numeric | YES | - |
| `estimated_repair_cost_eur` | numeric | YES | - |
| `warranty_status` | varchar(50) | YES | 'unchecked'::character varying |
| `metadata` | jsonb | YES | '{}'::jsonb |
| `created_at` | timestamp without time zone | YES | now() |
| `radix_device_id` | varchar(100) | YES | - |
| `radix_part_id` | varchar(100) | YES | - |
| `device_serial` | varchar(100) | YES | - |

**Foreign Keys:**
- `manufacturer_id` → `krai_core.manufacturers.id`
- `ticket_id` → `krai_pm.service_tickets.id`

### krai_pm.predictions
> Model outputs for predictive maintenance.

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `device_serial_hash` | varchar(64) | YES | - |
| `prediction_type` | varchar(50) | NO | - |
| `target_part_category` | varchar(50) | YES | - |
| `predicted_event_date` | date | YES | - |
| `predicted_remaining_pages` | integer | YES | - |
| `risk_score` | double precision | YES | - |
| `confidence` | double precision | YES | - |
| `model_name` | varchar(100) | NO | - |
| `model_version` | varchar(50) | NO | - |
| `mlflow_run_id` | varchar(100) | YES | - |
| `created_at` | timestamp with time zone | YES | now() |
| `ground_truth_event_date` | date | YES | - |
| `ground_truth_set_at` | timestamp with time zone | YES | - |
| `metadata` | jsonb | YES | '{}'::jsonb |

### krai_pm.service_routes
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | integer | NO | nextval('krai_pm.service_routes_id_seq'::regclass) |
| `activity_id` | varchar(255) | NO | - |
| `route_sequence` | integer | YES | - |
| `employee_id` | varchar(255) | YES | - |
| `employee_name` | varchar(255) | YES | - |
| `from_address` | text | YES | - |
| `to_address` | text | YES | - |
| `departure_time` | timestamp without time zone | YES | - |
| `arrival_time` | timestamp without time zone | YES | - |
| `duration_minutes` | integer | YES | - |
| `distance_km` | numeric | YES | - |
| `route_calculation_method` | varchar(50) | YES | - |
| `metadata` | jsonb | YES | '{}'::jsonb |
| `created_at` | timestamp without time zone | YES | now() |
| `updated_at` | timestamp without time zone | YES | now() |

**Foreign Keys:**
- `activity_id` → `krai_pm.service_tickets.id`

### krai_pm.service_tickets
> Harmonized service tickets from multiple sources.

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | varchar(255) | NO | gen_random_uuid() |
| `source_system` | varchar(50) | NO | - |
| `source_ticket_id` | varchar(200) | NO | - |
| `manufacturer_id` | uuid | YES | - |
| `product_id` | uuid | YES | - |
| `model_string_raw` | text | YES | - |
| `created_at_source` | timestamp with time zone | YES | - |
| `problem_short` | text | YES | - |
| `problem_long` | text | YES | - |
| `solution_text` | text | YES | - |
| `error_codes` | _text | YES | - |
| `replaced_parts` | _text | YES | - |
| `replaced_part_categories` | _text | YES | - |
| `repair_time_minutes` | integer | YES | - |
| `ticket_embedding` | vector(768) | YES | - |
| `metadata` | jsonb | YES | - |
| `ingested_at` | timestamp with time zone | YES | now() |
| `device_id` | varchar(255) | YES | - |
| `device_serial_number` | varchar(255) | YES | - |
| `device_model` | varchar(255) | YES | - |
| `customer_id` | varchar(255) | YES | - |
| `customer_name` | varchar(255) | YES | - |
| `customer_address` | text | YES | - |
| `service_location_address` | text | YES | - |
| `employee_id` | varchar(255) | YES | - |
| `employee_name` | varchar(255) | YES | - |
| `device_runtime_hours` | integer | YES | - |
| `toner_level` | integer | YES | - |
| `total_travel_time_minutes` | integer | YES | - |
| `total_travel_distance_km` | numeric | YES | - |
| `scheduled_date` | timestamp without time zone | YES | - |
| `completed_date` | timestamp without time zone | YES | - |
| `activity_state` | varchar(100) | YES | - |
| `radix_device_id` | varchar(100) | YES | - |
| `device_serial` | varchar(100) | YES | - |
| `part_numbers` | _text | YES | '{}'::text[] |

**Foreign Keys:**
- `manufacturer_id` → `krai_core.manufacturers.id`
- `product_id` → `krai_core.products.id`

### krai_pm.vw_daily_routes
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `service_date` | date | YES | - |
| `employee_id` | varchar(255) | YES | - |
| `employee_name` | varchar(255) | YES | - |
| `stop_count` | bigint | YES | - |
| `total_travel_minutes` | bigint | YES | - |
| `total_distance_km` | numeric | YES | - |

### krai_pm.vw_service_efficiency
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | varchar(255) | YES | - |
| `device_id` | varchar(255) | YES | - |
| `customer_name` | varchar(255) | YES | - |
| `employee_name` | varchar(255) | YES | - |
| `problem_short` | text | YES | - |
| `repair_time_minutes` | integer | YES | - |
| `total_travel_time_minutes` | integer | YES | - |
| `total_service_time_minutes` | integer | YES | - |
| `completed_date` | timestamp without time zone | YES | - |
| `activity_state` | varchar(100) | YES | - |

### krai_pm.vw_warranty_analysis
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `manufacturer_name` | varchar(100) | YES | - |
| `part_category` | varchar(50) | YES | - |
| `total_replacements` | bigint | YES | - |
| `warranty_eligible_count` | bigint | YES | - |
| `warranty_rate_pct` | numeric | YES | - |
| `avg_nominal_lifetime` | integer | YES | - |
| `avg_actual_runtime` | integer | YES | - |
| `avg_mismatch_ratio` | numeric | YES | - |
| `total_repair_cost_eur` | numeric | YES | - |

### krai_pm.vw_warranty_analysis_detailed
> Warranty analysis with device and part IDs for complete traceability to source systems

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `manufacturer_name` | varchar(100) | YES | - |
| `part_category` | varchar(50) | YES | - |
| `radix_device_id` | varchar(100) | YES | - |
| `radix_part_id` | varchar(100) | YES | - |
| `total_replacements` | bigint | YES | - |
| `warranty_eligible_count` | bigint | YES | - |
| `warranty_rate_pct` | numeric | YES | - |
| `avg_nominal_lifetime` | integer | YES | - |
| `avg_actual_runtime` | integer | YES | - |
| `avg_mismatch_ratio` | numeric | YES | - |
| `total_repair_cost_eur` | numeric | YES | - |
| `affected_device_serials` | text | YES | - |

## krai_system

*Pipeline, Queue, Alerts, Metrics, Migrations, Stage-Tracking*

### krai_system.alert_configurations
> Stores alert rules and recipients configured via Dashboard

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `rule_name` | varchar(100) | NO | - |
| `description` | text | YES | - |
| `is_enabled` | boolean | NO | true |
| `error_types` | _varchar | YES | - |
| `stages` | _varchar | YES | - |
| `severity_threshold` | varchar(20) | NO | 'medium'::character varying |
| `error_count_threshold` | integer | NO | 5 |
| `time_window_minutes` | integer | NO | 15 |
| `aggregation_window_minutes` | integer | NO | 5 |
| `email_recipients` | _text | YES | - |
| `slack_webhooks` | _text | YES | - |
| `created_by` | uuid | YES | - |
| `created_at` | timestamp without time zone | NO | CURRENT_TIMESTAMP |
| `updated_at` | timestamp without time zone | NO | CURRENT_TIMESTAMP |

### krai_system.alert_queue
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | YES | - |
| `alert_type` | varchar(50) | YES | - |
| `severity` | varchar(20) | YES | - |
| `message` | text | YES | - |
| `details` | jsonb | YES | - |
| `source_service` | varchar(100) | YES | - |
| `correlation_id` | varchar(100) | YES | - |
| `aggregation_key` | varchar(200) | YES | - |
| `aggregation_count` | integer | YES | - |
| `first_occurrence` | timestamp without time zone | YES | - |
| `last_occurrence` | timestamp without time zone | YES | - |
| `status` | varchar(20) | YES | - |
| `sent_at` | timestamp without time zone | YES | - |
| `created_at` | timestamp without time zone | YES | - |

### krai_system.alerts
> Alert queue for aggregation; recipients/webhooks metadata in alert_configurations

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `alert_type` | varchar(50) | NO | - |
| `severity` | varchar(20) | NO | - |
| `message` | text | NO | - |
| `details` | jsonb | YES | '{}'::jsonb |
| `source_service` | varchar(100) | YES | - |
| `correlation_id` | varchar(100) | YES | - |
| `aggregation_key` | varchar(200) | YES | - |
| `aggregation_count` | integer | NO | 1 |
| `first_occurrence` | timestamp without time zone | NO | CURRENT_TIMESTAMP |
| `last_occurrence` | timestamp without time zone | NO | CURRENT_TIMESTAMP |
| `status` | varchar(20) | NO | 'pending'::character varying |
| `sent_at` | timestamp without time zone | YES | - |
| `created_at` | timestamp without time zone | NO | CURRENT_TIMESTAMP |

### krai_system.audit_log
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `table_name` | varchar(100) | NO | - |
| `record_id` | uuid | NO | - |
| `operation` | varchar(10) | NO | - |
| `old_values` | jsonb | YES | - |
| `new_values` | jsonb | YES | - |
| `changed_by` | varchar(100) | YES | - |
| `changed_at` | timestamp with time zone | YES | now() |
| `session_id` | varchar(100) | YES | - |
| `ip_address` | inet | YES | - |
| `user_agent` | text | YES | - |

### krai_system.benchmark_documents
> Stores selected benchmark documents for performance testing and baseline measurements

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `document_id` | uuid | NO | - |
| `snapshot_id` | varchar(255) | NO | - |
| `file_size` | bigint | YES | - |
| `selected_at` | timestamp with time zone | YES | now() |
| `metadata` | jsonb | YES | '{}'::jsonb |

**Foreign Keys:**
- `document_id` → `krai_core.documents.id`

### krai_system.crawled_pages
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `crawl_job_id` | uuid | YES | - |
| `url` | text | NO | - |
| `content_hash` | text | YES | - |
| `content_text` | text | YES | - |
| `metadata` | jsonb | YES | - |
| `crawled_at` | timestamp with time zone | YES | now() |

**Foreign Keys:**
- `crawl_job_id` → `krai_system.manufacturer_crawl_jobs.id`

### krai_system.health_checks
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `service_name` | varchar(100) | NO | - |
| `check_type` | varchar(50) | NO | - |
| `status` | varchar(20) | NO | - |
| `response_time_ms` | integer | YES | - |
| `error_message` | text | YES | - |
| `details` | jsonb | YES | '{}'::jsonb |
| `checked_at` | timestamp with time zone | YES | now() |

### krai_system.link_scraping_jobs
> Web scraping jobs for enriching links with actual content

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `url` | text | NO | - |
| `manufacturer_id` | uuid | YES | - |
| `document_id` | uuid | YES | - |
| `source_link_id` | uuid | YES | - |
| `scrape_status` | varchar(20) | NO | 'pending'::character varying |
| `scrape_priority` | integer | YES | 0 |
| `retry_count` | integer | YES | 0 |
| `scraped_content` | text | YES | - |
| `content_hash` | varchar(64) | YES | - |
| `content_type` | varchar(100) | YES | - |
| `scraped_metadata` | jsonb | YES | '{}'::jsonb |
| `scrape_error` | text | YES | - |
| `created_at` | timestamp with time zone | YES | now() |
| `scraped_at` | timestamp with time zone | YES | - |
| `updated_at` | timestamp with time zone | YES | now() |
| `next_retry_at` | timestamp with time zone | YES | - |

**Foreign Keys:**
- `manufacturer_id` → `krai_core.manufacturers.id`
- `document_id` → `krai_core.documents.id`
- `source_link_id` → `krai_content.links.id`

### krai_system.manufacturer_crawl_jobs
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `schedule_id` | uuid | YES | - |
| `manufacturer_id` | text | NO | - |
| `status` | text | YES | 'pending'::text |
| `pages_crawled` | integer | YES | 0 |
| `started_at` | timestamp with time zone | YES | - |
| `completed_at` | timestamp with time zone | YES | - |
| `error_message` | text | YES | - |
| `created_at` | timestamp with time zone | YES | now() |

**Foreign Keys:**
- `schedule_id` → `krai_system.manufacturer_crawl_schedules.id`

### krai_system.manufacturer_crawl_schedules
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `manufacturer_id` | text | NO | - |
| `crawl_type` | text | NO | - |
| `start_url` | text | NO | - |
| `max_pages` | integer | YES | 100 |
| `max_depth` | integer | YES | 3 |
| `schedule_cron` | text | YES | - |
| `next_run` | timestamp with time zone | YES | - |
| `enabled` | boolean | YES | true |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |
| `url_patterns` | _text | YES | - |
| `exclude_patterns` | _text | YES | - |
| `crawl_options` | jsonb | YES | - |
| `next_run_at` | timestamp with time zone | YES | - |
| `last_run_at` | timestamp with time zone | YES | - |

### krai_system.migrations
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `migration_name` | varchar(255) | NO | - |
| `applied_at` | timestamp with time zone | YES | now() |
| `description` | text | YES | - |

### krai_system.performance_baselines
> Stores performance baselines and measurements

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `stage_name` | varchar(50) | NO | - |
| `baseline_avg_seconds` | numeric | NO | - |
| `baseline_p50_seconds` | numeric | NO | - |
| `baseline_p95_seconds` | numeric | NO | - |
| `baseline_p99_seconds` | numeric | NO | - |
| `current_avg_seconds` | numeric | YES | - |
| `current_p50_seconds` | numeric | YES | - |
| `current_p95_seconds` | numeric | YES | - |
| `current_p99_seconds` | numeric | YES | - |
| `improvement_percentage` | numeric | YES | - |
| `test_document_ids` | _uuid | YES | - |
| `measurement_date` | timestamp without time zone | NO | CURRENT_TIMESTAMP |
| `notes` | text | YES | - |
| `created_at` | timestamp without time zone | NO | CURRENT_TIMESTAMP |

### krai_system.pipeline_errors
> Primary table for error tracking and Dashboard queries

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `correlation_id` | varchar(100) | NO | - |
| `stage_name` | varchar(100) | NO | - |
| `error_type` | varchar(100) | NO | - |
| `error_message` | text | NO | - |
| `error_details` | jsonb | YES | '{}'::jsonb |
| `document_id` | uuid | YES | - |
| `file_path` | text | YES | - |
| `metadata` | jsonb | YES | '{}'::jsonb |
| `severity` | varchar(20) | YES | 'medium'::character varying |
| `is_resolved` | boolean | YES | false |
| `resolved_by` | varchar(100) | YES | - |
| `resolved_at` | timestamp with time zone | YES | - |
| `resolution_notes` | text | YES | - |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |
| `error_id` | varchar(100) | NO | - |
| `error_category` | varchar(50) | YES | - |
| `stack_trace` | text | YES | - |
| `context` | jsonb | YES | '{}'::jsonb |
| `retry_count` | integer | NO | 0 |
| `max_retries` | integer | NO | 3 |
| `status` | varchar(20) | NO | 'pending'::character varying |
| `is_transient` | boolean | NO | true |
| `next_retry_at` | timestamp without time zone | YES | - |

### krai_system.processing_queue
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `document_id` | uuid | YES | - |
| `chunk_id` | uuid | YES | - |
| `image_id` | uuid | YES | - |
| `video_id` | uuid | YES | - |
| `task_type` | varchar(50) | NO | - |
| `priority` | integer | YES | 5 |
| `status` | varchar(20) | YES | 'pending'::character varying |
| `scheduled_at` | timestamp with time zone | YES | now() |
| `started_at` | timestamp with time zone | YES | - |
| `completed_at` | timestamp with time zone | YES | - |
| `error_message` | text | YES | - |
| `retry_count` | integer | YES | 0 |
| `max_retries` | integer | YES | 3 |
| `created_at` | timestamp with time zone | YES | now() |
| `stage` | varchar(50) | NO | 'storage'::character varying |
| `payload` | jsonb | YES | '{}'::jsonb |
| `updated_at` | timestamp with time zone | YES | now() |

**Foreign Keys:**
- `video_id` → `krai_content.instructional_videos.id`
- `document_id` → `krai_core.documents.id`
- `chunk_id` → `krai_intelligence.chunks.id`
- `image_id` → `krai_content.images.id`

### krai_system.prompt_templates
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | integer | NO | nextval('krai_system.prompt_templates_id_seq'::regclass) |
| `title` | varchar(100) | NO | - |
| `description` | varchar(255) | YES | - |
| `prompt_text` | text | NO | - |
| `category` | varchar(50) | NO | 'general'::character varying |
| `icon` | varchar(50) | YES | 'heroicon-o-chat-bubble-left'::character varying |
| `sort_order` | integer | NO | 0 |
| `is_active` | boolean | NO | true |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

### krai_system.retry_policies
> Configurable retry policies per service/stage

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `policy_name` | varchar(100) | NO | - |
| `service_name` | varchar(50) | NO | - |
| `stage_name` | varchar(50) | YES | - |
| `max_retries` | integer | NO | 3 |
| `base_delay_seconds` | numeric | NO | 1.0 |
| `max_delay_seconds` | numeric | NO | 60.0 |
| `exponential_base` | numeric | NO | 2.0 |
| `jitter_enabled` | boolean | NO | true |
| `circuit_breaker_enabled` | boolean | NO | false |
| `circuit_breaker_threshold` | integer | NO | 5 |
| `circuit_breaker_timeout_seconds` | integer | NO | 60 |
| `created_at` | timestamp without time zone | NO | CURRENT_TIMESTAMP |
| `updated_at` | timestamp without time zone | NO | CURRENT_TIMESTAMP |

### krai_system.stage_completion_markers
> Tracks stage completion with data hashing for idempotency checks

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `document_id` | uuid | NO | - |
| `stage_name` | varchar(100) | NO | - |
| `completed_at` | timestamp with time zone | YES | now() |
| `data_hash` | varchar(64) | YES | - |
| `metadata` | jsonb | YES | '{}'::jsonb |

### krai_system.stage_metrics
> Real-time stage processing metrics for each document

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `document_id` | uuid | NO | - |
| `stage_name` | varchar(50) | NO | - |
| `processing_time` | numeric | NO | - |
| `success` | boolean | NO | true |
| `error_message` | text | YES | - |
| `correlation_id` | varchar(100) | YES | - |
| `created_at` | timestamp without time zone | NO | CURRENT_TIMESTAMP |

**Foreign Keys:**
- `document_id` → `krai_core.documents.id`

### krai_system.stage_tracking
> Tracks pipeline stage execution per document

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `document_id` | uuid | NO | - |
| `stage_number` | integer | NO | - |
| `stage_name` | varchar(100) | NO | - |
| `status` | varchar(50) | NO | - |
| `started_at` | timestamp with time zone | YES | - |
| `completed_at` | timestamp with time zone | YES | - |
| `error_message` | text | YES | - |
| `metadata` | jsonb | YES | - |
| `created_at` | timestamp with time zone | YES | CURRENT_TIMESTAMP |
| `updated_at` | timestamp with time zone | YES | CURRENT_TIMESTAMP |

**Foreign Keys:**
- `document_id` → `krai_core.documents.id`

### krai_system.system_metrics
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `metric_name` | varchar(100) | NO | - |
| `metric_value` | numeric | YES | - |
| `metric_unit` | varchar(20) | YES | - |
| `metric_category` | varchar(50) | YES | - |
| `collection_timestamp` | timestamp with time zone | YES | now() |
| `server_instance` | varchar(100) | YES | - |
| `additional_context` | jsonb | YES | '{}'::jsonb |

## krai_users

*Benutzer und Sessions*

### krai_users.chat_messages
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | bigint | NO | nextval('krai_users.chat_messages_id_seq'::regclass) |
| `session_id` | uuid | NO | - |
| `role` | varchar(20) | NO | - |
| `content` | text | NO | - |
| `created_at` | timestamp with time zone | YES | now() |

**Foreign Keys:**
- `session_id` → `krai_users.chat_sessions.id`

### krai_users.chat_sessions
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `user_id` | uuid | YES | - |
| `session_key` | varchar(128) | NO | - |
| `title` | varchar(255) | YES | - |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |
| `last_active` | timestamp with time zone | YES | now() |

**Foreign Keys:**
- `user_id` → `krai_users.users.id`

### krai_users.token_blacklist
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `jti` | varchar(255) | NO | - |
| `user_id` | uuid | NO | - |
| `token_type` | varchar(20) | NO | - |
| `expires_at` | timestamp with time zone | NO | - |
| `blacklisted_at` | timestamp with time zone | NO | now() |
| `reason` | varchar(100) | YES | - |

### krai_users.user_sessions
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `user_id` | uuid | NO | - |
| `session_token` | varchar(255) | NO | - |
| `expires_at` | timestamp with time zone | NO | - |
| `created_at` | timestamp with time zone | YES | now() |

**Foreign Keys:**
- `user_id` → `krai_users.users.id`

### krai_users.users
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `preferred_manufacturer_id` | uuid | YES | - |
| `username` | varchar(100) | NO | - |
| `email` | varchar(255) | NO | - |
| `role` | varchar(50) | YES | 'user'::character varying |
| `created_at` | timestamp with time zone | YES | now() |
| `password_hash` | varchar(255) | YES | - |
| `first_name` | varchar(100) | YES | - |
| `last_name` | varchar(100) | YES | - |
| `is_active` | boolean | YES | true |
| `last_login` | timestamp with time zone | YES | - |
| `status` | varchar(20) | YES | 'active'::character varying |
| `is_verified` | boolean | YES | false |
| `login_count` | integer | YES | 0 |
| `failed_login_attempts` | integer | YES | 0 |
| `updated_at` | timestamp with time zone | YES | now() |
| `locked_until` | timestamp with time zone | YES | - |
| `permissions` | jsonb | YES | '[]'::jsonb |

**Foreign Keys:**
- `preferred_manufacturer_id` → `krai_core.manufacturers.id`

## public

### public.vw_device_lifecycle
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | YES | - |
| `device_serial_hash` | varchar(64) | YES | - |
| `product_id` | uuid | YES | - |
| `counter_total` | bigint | YES | - |
| `counter_color` | bigint | YES | - |
| `counter_bw` | bigint | YES | - |
| `measured_at` | timestamp with time zone | YES | - |
| `toner_levels` | jsonb | YES | - |
| `maintenance_events` | jsonb | YES | - |
| `metadata` | jsonb | YES | - |
| `ingested_at` | timestamp with time zone | YES | - |

### public.vw_part_lifetimes
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | YES | - |
| `manufacturer_id` | uuid | YES | - |
| `product_id` | uuid | YES | - |
| `part_category` | varchar(50) | YES | - |
| `part_number` | varchar(100) | YES | - |
| `nominal_lifetime_pages` | integer | YES | - |
| `color_channel` | varchar(10) | YES | - |
| `source` | varchar(50) | YES | - |
| `metadata` | jsonb | YES | - |
| `ingested_at` | timestamp with time zone | YES | - |

### public.vw_predictions
| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | YES | - |
| `device_serial_hash` | varchar(64) | YES | - |
| `prediction_type` | varchar(50) | YES | - |
| `target_part_category` | varchar(50) | YES | - |
| `predicted_event_date` | date | YES | - |
| `predicted_remaining_pages` | integer | YES | - |
| `risk_score` | double precision | YES | - |
| `confidence` | double precision | YES | - |
| `model_name` | varchar(100) | YES | - |
| `model_version` | varchar(50) | YES | - |
| `mlflow_run_id` | varchar(100) | YES | - |
| `created_at` | timestamp with time zone | YES | - |
| `ground_truth_event_date` | date | YES | - |
| `ground_truth_set_at` | timestamp with time zone | YES | - |
