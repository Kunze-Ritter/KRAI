# KRAI Database Schema Documentation
================================================================================

**Zuletzt aktualisiert:** 25.03.2026

**Quelle:** PostgreSQL Database (Production Structure - Migration from Supabase completed November 2024, KRAI-002)

**Setup:** Siehe `database/README.md` für PostgreSQL Installation

**Aktueller Repo-Stand bei Migrationen:** `029_fix_match_functions.sql`

## ⚠️ WICHTIGE INFORMATIONEN

### PostgreSQL Setup
- **Database:** PostgreSQL 15+ mit pgvector Extension
- **Migrationen:** `database/migrations_postgresql/` (aktiver inkrementeller Satz, derzeit `001` bis `029`)
- **Historischer Kontext:** `database/migrations/README.md` (nur Hinweise, kein aktiver Migrationspfad)

### Embeddings Storage
- **Embeddings sind in `krai_intelligence.chunks` als Spalte `embedding` gespeichert!**
- Es gibt KEIN separates `krai_embeddings` Schema
- Spalte: `embedding` (Typ: `vector(768)`)
- View: `public.vw_embeddings` ist ein ALIAS für `public.vw_chunks`

### View Naming Convention
- Alle Views nutzen `vw_` Prefix
- Views sind im `public` Schema
- Tabellen sind in `krai_*` Schemas
- Views werden automatisch via Migration `002_views.sql` erstellt

### Wichtige Tabellen für Processing
- `krai_core.documents` - Haupttabelle für Dokumente
- `krai_core.products` - Produkte
- `krai_core.manufacturers` - Hersteller
- `krai_intelligence.chunks` - Text-Chunks mit Embeddings
- `krai_intelligence.error_codes` - Fehlercodes
- `krai_content.videos` - Videos
- `krai_content.links` - Links
- `krai_content.images` - Bilder
- `krai_parts.parts_catalog` - Ersatzteile
- `krai_system.processing_queue` - Pipeline-Queue

### ⚠️ Known Column Name Traps (Historisch bedingte Fehlerquellen)

| FALSCH | RICHTIG | Tabelle | Beschreibung |
|--------|---------|---------|--------------|
| `chunk_text` | `text_chunk` | `krai_intelligence.chunks` | Text-Inhalt |
| `enrichment_error` | `metadata->>'enrichment_error'` | `krai_content.videos` | Keine eigene Spalte, in JSONB |
| `tags` | `metadata->>'tags'` | `krai_content.videos` | Keine eigene Spalte, in JSONB |
| `error_code` | `error_code` | `krai_intelligence.error_codes` | Immer Kleinbuchstaben! |
| `solution_text` | `solution_technician_text` | `krai_intelligence.error_codes` | Seit Migration 025 aufgeteilt in 3 Spalten |
| `requires_technician` | *(entfernt)* | `krai_intelligence.error_codes` | Seit Migration 025 gelöscht |

### 🔑 Wichtige Query-Muster

```sql
-- Alle Chunks mit Embeddings (NEU: embedding Spalte direkt in chunks!)
SELECT id, text_chunk, embedding FROM krai_intelligence.chunks
WHERE embedding IS NOT NULL LIMIT 10;

-- Videos mit Fehler (metadata JSONB)
SELECT id, title, metadata->>'enrichment_error' as error
FROM krai_content.videos
WHERE metadata->>'enrichment_error' IS NOT NULL;

-- Error Code Hierarchy (ab Migration 018)
SELECT error_code, error_description, parent_code, is_category
FROM krai_intelligence.error_codes
WHERE parent_code = '13.B9' ORDER BY error_code;
```

---

## Table of Contents

- [krai_content](#krai-content) (5 Tabellen)
- [krai_core](#krai-core) (11 Tabellen)
- [krai_intelligence](#krai-intelligence) (13 Tabellen)
- [krai_parts](#krai-parts) (2 Tabellen)
- [krai_system](#krai-system) (5 Tabellen)
- [krai_users](#krai-users) (2 Tabellen)

---

## krai_content

### krai_content.images

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `document_id` | uuid | YES | - |
| `chunk_id` | uuid | YES | - |
| `filename` | character varying(255) | YES | - |
| `original_filename` | character varying(255) | YES | - |
| `storage_path` | text | YES | - |
| `storage_url` | text | NO | - |
| `file_size` | int4 | YES | - |
| `image_format` | character varying(10) | YES | - |
| `width_px` | int4 | YES | - |
| `height_px` | int4 | YES | - |
| `page_number` | int4 | YES | - |
| `image_index` | int4 | YES | - |
| `image_type` | character varying(50) | YES | - |
| `ai_description` | text | YES | - |
| `ai_confidence` | numeric | YES | - |
| `contains_text` | bool | YES | false |
| `ocr_text` | text | YES | - |
| `ocr_confidence` | numeric | YES | - |
| `manual_description` | text | YES | - |
| `tags` | _text | YES | - |
| `file_hash` | character varying(64) | YES | - |
| `created_at` | timestamptz | YES | now() |
| `updated_at` | timestamptz | YES | now() |
| `figure_number` | character varying(50) | YES | - |
| `figure_context` | text | YES | - |
| `context_caption` | text | YES | - |
| `page_header` | text | YES | - |
| `surrounding_paragraphs` | _text | YES | - |
| `related_error_codes` | _text | YES | - |
| `related_products` | _text | YES | - |
| `related_chunks` | _uuid | YES | - |
| `context_embedding` | vector | YES | - |
| `figure_reference` | text | YES | - |

### krai_content.links

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `document_id` | uuid | NO | - |
| `url` | text | NO | - |
| `link_type` | character varying(50) | NO | 'external'::character varying |
| `page_number` | int4 | NO | - |
| `description` | text | YES | - |
| `position_data` | jsonb | YES | - |
| `is_active` | bool | YES | true |
| `created_at` | timestamptz | YES | now() |
| `updated_at` | timestamptz | YES | now() |
| `video_id` | uuid | YES | - |
| `metadata` | jsonb | YES | '{}'::jsonb |
| `link_category` | character varying(50) | YES | - |
| `confidence_score` | numeric | YES | 0.0 |
| `manufacturer_id` | uuid | YES | - |
| `series_id` | uuid | YES | - |
| `related_error_codes` | _text | YES | - |
| `context_description` | text | YES | - |
| `related_chunks` | _uuid | YES | - |
| `context_embedding` | vector | YES | - |

### krai_content.print_defects

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `manufacturer_id` | uuid | NO | - |
| `product_id` | uuid | YES | - |
| `original_image_id` | uuid | YES | - |
| `defect_name` | character varying(100) | NO | - |
| `defect_category` | character varying(50) | YES | - |
| `defect_description` | text | YES | - |
| `example_image_url` | text | YES | - |
| `annotated_image_url` | text | YES | - |
| `detection_confidence` | numeric | YES | - |
| `common_causes` | jsonb | YES | '[]'::jsonb |
| `recommended_solutions` | jsonb | YES | '[]'::jsonb |
| `related_error_codes` | _text | YES | - |
| `created_at` | timestamptz | YES | now() |

### krai_content.video_products

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `video_id` | uuid | NO | - |
| `product_id` | uuid | NO | - |
| `created_at` | timestamptz | YES | now() |

### krai_content.videos

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `link_id` | uuid | YES | - |
| `youtube_id` | character varying(20) | YES | - |
| `platform` | character varying(20) | YES | - |
| `video_url` | text | YES | - |
| `title` | character varying(500) | NO | - |
| `description` | text | YES | - |
| `thumbnail_url` | text | YES | - |
| `duration` | int4 | YES | - |
| `channel_id` | character varying(50) | YES | - |
| `channel_title` | character varying(200) | YES | - |
| `published_at` | timestamptz | YES | - |
| `manufacturer_id` | uuid | YES | - |
| `series_id` | uuid | YES | - |
| `document_id` | uuid | YES | - |
| `metadata` | jsonb | YES | - |
| `created_at` | timestamptz | YES | now() |
| `updated_at` | timestamptz | YES | now() |
| `enriched_at` | timestamptz | YES | now() |
| `context_description` | text | YES | - |
| `related_products` | _text | YES | - |
| `related_chunks` | _uuid | YES | - |
| `page_number` | int4 | YES | - |
| `context_embedding` | vector | YES | - |

## krai_core

### krai_core.document_products

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `document_id` | uuid | NO | - |
| `product_id` | uuid | NO | - |
| `is_primary_product` | bool | YES | false |
| `confidence_score` | numeric | YES | 0.80 |
| `extraction_method` | character varying(50) | YES | - |
| `page_numbers` | _int4 | YES | - |
| `created_at` | timestamptz | YES | now() |
| `updated_at` | timestamptz | YES | now() |

### krai_core.document_relationships

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `primary_document_id` | uuid | NO | - |
| `secondary_document_id` | uuid | NO | - |
| `relationship_type` | character varying(50) | NO | - |
| `relationship_strength` | numeric | YES | 0.5 |
| `auto_discovered` | bool | YES | true |
| `manual_verification` | bool | YES | false |
| `verification_date` | timestamptz | YES | - |
| `verified_by` | character varying(100) | YES | - |
| `notes` | text | YES | - |
| `created_at` | timestamptz | YES | now() |

### krai_core.documents

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `filename` | character varying(255) | NO | - |
| `file_size` | int8 | YES | - |
| `file_hash` | character varying(64) | YES | - |
| `storage_path` | text | YES | - |
| `document_type` | character varying(100) | YES | - |
| `language` | character varying(10) | YES | 'en'::character varying |
| `version` | character varying(50) | YES | - |
| `publish_date` | date | YES | - |
| `page_count` | int4 | YES | - |
| `word_count` | int4 | YES | - |
| `character_count` | int4 | YES | - |
| `extracted_metadata` | jsonb | YES | '{}'::jsonb |
| `processing_status` | character varying(50) | YES | 'pending'::character varying |
| `processing_results` | jsonb | YES | - |
| `processing_error` | text | YES | - |
| `stage_status` | jsonb | YES | '{}'::jsonb |
| `confidence_score` | numeric | YES | - |
| `ocr_confidence` | numeric | YES | - |
| `manual_review_required` | bool | YES | false |
| `manual_review_completed` | bool | YES | false |
| `manual_review_notes` | text | YES | - |
| `manufacturer` | character varying(100) | YES | - |
| `series` | character varying(100) | YES | - |
| `models` | _text | YES | - |
| `created_at` | timestamptz | YES | now() |
| `updated_at` | timestamptz | YES | now() |
| `priority_level` | int4 | YES | 5 |
| `manufacturer_id` | uuid | YES | - |

### krai_core.manufacturers

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `name` | character varying(100) | NO | - |
| `short_name` | character varying(10) | YES | - |
| `country` | character varying(50) | YES | - |
| `founded_year` | int4 | YES | - |
| `website` | character varying(255) | YES | - |
| `support_email` | character varying(255) | YES | - |
| `support_phone` | character varying(50) | YES | - |
| `logo_url` | text | YES | - |
| `is_competitor` | bool | YES | false |
| `market_share_percent` | numeric | YES | - |
| `annual_revenue_usd` | int8 | YES | - |
| `employee_count` | int4 | YES | - |
| `headquarters_address` | text | YES | - |
| `stock_symbol` | character varying(10) | YES | - |
| `primary_business_segment` | character varying(100) | YES | - |
| `created_at` | timestamptz | YES | now() |
| `updated_at` | timestamptz | YES | now() |

### krai_core.oem_relationships

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `brand_manufacturer` | character varying(100) | NO | - |
| `brand_series_pattern` | character varying(200) | NO | - |
| `oem_manufacturer` | character varying(100) | NO | - |
| `relationship_type` | character varying(50) | YES | 'engine'::character varying |
| `applies_to` | _text | YES | ARRAY['error_codes'::text, 'parts'::t... |
| `notes` | text | YES | - |
| `confidence` | float8 | YES | 1.0 |
| `source` | character varying(100) | YES | 'manual'::character varying |
| `verified` | bool | YES | false |
| `created_at` | timestamptz | YES | now() |
| `updated_at` | timestamptz | YES | now() |

### krai_core.option_dependencies

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `option_id` | uuid | NO | - |
| `depends_on_option_id` | uuid | NO | - |
| `dependency_type` | character varying(20) | NO | - |
| `notes` | text | YES | - |
| `created_at` | timestamptz | YES | now() |
| `updated_at` | timestamptz | YES | now() |

### krai_core.product_accessories

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `product_id` | uuid | NO | - |
| `accessory_id` | uuid | NO | - |
| `compatibility_type` | character varying(50) | NO | - |
| `installation_required` | bool | YES | false |
| `quantity_min` | int4 | YES | 1 |
| `quantity_max` | int4 | YES | 1 |
| `notes` | text | YES | - |
| `created_at` | timestamptz | YES | now() |
| `priority` | int4 | YES | 0 |
| `compatibility_notes` | text | YES | - |
| `is_standard` | bool | YES | false |
| `mounting_position` | character varying(20) | YES | - |
| `slot_number` | int4 | YES | - |
| `max_quantity` | int4 | YES | 1 |

### krai_core.product_configurations

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `configuration_name` | character varying(200) | YES | - |
| `base_product_id` | uuid | NO | - |
| `accessories` | jsonb | YES | '[]'::jsonb |
| `is_valid` | bool | YES | true |
| `validation_errors` | jsonb | YES | '[]'::jsonb |
| `created_at` | timestamptz | YES | now() |
| `updated_at` | timestamptz | YES | now() |
| `created_by` | character varying(100) | YES | - |

### krai_core.product_series

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `manufacturer_id` | uuid | NO | - |
| `series_name` | character varying(100) | NO | - |
| `series_code` | character varying(50) | YES | - |
| `launch_date` | date | YES | - |
| `end_of_life_date` | date | YES | - |
| `target_market` | character varying(100) | YES | - |
| `price_range` | character varying(50) | YES | - |
| `key_features` | jsonb | YES | '{}'::jsonb |
| `series_description` | text | YES | - |
| `marketing_name` | character varying(150) | YES | - |
| `successor_series_id` | uuid | YES | - |
| `created_at` | timestamptz | YES | now() |
| `updated_at` | timestamptz | YES | now() |
| `model_pattern` | text | YES | - |

### krai_core.products

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `manufacturer_id` | uuid | YES | - |
| `series_id` | uuid | YES | - |
| `model_number` | character varying(100) | NO | - |
| `product_type` | character varying(50) | NO | 'laser_printer'::character varying |
| `created_at` | timestamptz | YES | now() |
| `updated_at` | timestamptz | YES | now() |
| `specifications` | jsonb | YES | '{}'::jsonb |
| `pricing` | jsonb | YES | '{}'::jsonb |
| `lifecycle` | jsonb | YES | '{}'::jsonb |
| `urls` | jsonb | YES | '{}'::jsonb |
| `metadata` | jsonb | YES | '{}'::jsonb |
| `oem_manufacturer` | character varying(100) | YES | - |
| `oem_relationship_type` | character varying(50) | YES | - |
| `oem_notes` | text | YES | - |
| `product_code` | character varying(10) | YES | - |
| `article_code` | character varying(50) | YES | - |

### krai_core.products_backup

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | YES | - |
| `parent_id` | uuid | YES | - |
| `manufacturer_id` | uuid | YES | - |
| `series_id` | uuid | YES | - |
| `model_number` | character varying(100) | YES | - |
| `model_name` | character varying(200) | YES | - |
| `product_type` | character varying(50) | YES | - |
| `launch_date` | date | YES | - |
| `end_of_life_date` | date | YES | - |
| `msrp_usd` | numeric | YES | - |
| `weight_kg` | numeric | YES | - |
| `dimensions_mm` | jsonb | YES | - |
| `color_options` | _text | YES | - |
| `connectivity_options` | _text | YES | - |
| `print_technology` | character varying(50) | YES | - |
| `max_print_speed_ppm` | int4 | YES | - |
| `max_resolution_dpi` | int4 | YES | - |
| `max_paper_size` | character varying(20) | YES | - |
| `duplex_capable` | bool | YES | - |
| `network_capable` | bool | YES | - |
| `mobile_print_support` | bool | YES | - |
| `supported_languages` | _text | YES | - |
| `energy_star_certified` | bool | YES | - |
| `warranty_months` | int4 | YES | - |
| `service_manual_url` | text | YES | - |
| `parts_catalog_url` | text | YES | - |
| `driver_download_url` | text | YES | - |
| `firmware_version` | character varying(50) | YES | - |
| `option_dependencies` | jsonb | YES | - |
| `replacement_parts` | jsonb | YES | - |
| `common_issues` | jsonb | YES | - |
| `created_at` | timestamptz | YES | - |
| `updated_at` | timestamptz | YES | - |

## krai_intelligence

### krai_intelligence.agent_performance

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `date` | date | YES | - |
| `tool_name` | text | YES | - |
| `total_calls` | int8 | YES | - |
| `successful_calls` | int8 | YES | - |
| `failed_calls` | int8 | YES | - |
| `avg_response_time_ms` | numeric | YES | - |
| `p95_response_time_ms` | float8 | YES | - |
| `avg_results_count` | numeric | YES | - |

### krai_intelligence.chunks

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `document_id` | uuid | NO | - |
| `text_chunk` | text | NO | - |
| `chunk_index` | int4 | NO | - |
| `page_start` | int4 | YES | - |
| `page_end` | int4 | YES | - |
| `processing_status` | character varying(20) | YES | 'pending'::character varying |
| `fingerprint` | character varying(64) | NO | - |
| `metadata` | jsonb | YES | '{}'::jsonb |
| `created_at` | timestamptz | YES | now() |
| `updated_at` | timestamptz | YES | now() |
| `embedding` | vector | YES | - |
| `page_label_start` | character varying(20) | YES | - |
| `page_label_end` | character varying(20) | YES | - |

### Embeddings Storage (Kein separates Embeddings-Table)

Embeddings werden in `krai_intelligence.chunks.embedding` gespeichert.
Ein geplantes separates Embeddings-Table wurde nie implementiert.

### krai_intelligence.error_code_images

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `error_code_id` | uuid | NO | - |
| `image_id` | uuid | NO | - |
| `match_method` | text | YES | - |
| `match_confidence` | float8 | YES | 0.5 |
| `display_order` | int4 | YES | 0 |
| `created_at` | timestamptz | YES | now() |

### krai_intelligence.error_code_parts

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `error_code_id` | uuid | NO | - |
| `part_id` | uuid | NO | - |
| `relevance_score` | float8 | YES | 1.0 |
| `extraction_source` | text | YES | - |
| `created_at` | timestamptz | YES | now() |

### krai_intelligence.error_codes

> **Migration 025** (2026-03): `solution_text` und `requires_technician` wurden durch 3 Level-Spalten ersetzt.
> `manufacturer_id` ist jetzt für alle Rows befüllt (vorher NULL).

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `chunk_id` | uuid | YES | - |
| `document_id` | uuid | YES | - |
| `manufacturer_id` | uuid | NO | — (immer befüllt seit Migration 025) |
| `error_code` | character varying(20) | NO | - |
| `error_description` | text | YES | - |
| `solution_customer_text` | text | YES | Level 1 – Anwender-Schritte (HP: "Recommended action for customers") |
| `solution_agent_text` | text | YES | Level 2 – Call-Center (HP: "Recommended action for call-center agents") |
| `solution_technician_text` | text | YES | Level 3 – Techniker bevorzugt (HP: "Recommended action for onsite technicians"; andere Hersteller: gesamter Lösungstext) |
| `page_number` | int4 | YES | - |
| `confidence_score` | numeric | YES | - |
| `extraction_method` | character varying(50) | YES | - |
| `requires_parts` | bool | YES | false |
| `estimated_fix_time_minutes` | int4 | YES | - |
| `severity_level` | character varying(20) | YES | - |
| `created_at` | timestamptz | YES | now() |
| `image_id` | uuid | YES | - |
| `context_text` | text | YES | - |
| `metadata` | jsonb | YES | '{}'::jsonb |
| `product_id` | uuid | YES | - |
| `video_id` | uuid | YES | - |
| `parent_code` | text | YES | Übergeordneter Fehlercode (z.B. `13.B9` für `13.B9.Az`) |
| `is_category` | bool | YES | true = Kategorie-Eintrag (kein echter Fehler) |

### krai_intelligence.feedback

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `session_id` | text | NO | - |
| `message_id` | text | YES | - |
| `rating` | int4 | YES | - |
| `feedback_type` | text | YES | - |
| `comment` | text | YES | - |
| `created_at` | timestamptz | YES | now() |

### krai_intelligence.product_research_cache

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `manufacturer` | character varying(100) | NO | - |
| `model_number` | character varying(100) | NO | - |
| `series_name` | character varying(200) | YES | - |
| `series_description` | text | YES | - |
| `specifications` | jsonb | YES | '{}'::jsonb |
| `physical_specs` | jsonb | YES | '{}'::jsonb |
| `oem_manufacturer` | character varying(100) | YES | - |
| `oem_relationship_type` | character varying(50) | YES | - |
| `oem_notes` | text | YES | - |
| `launch_date` | date | YES | - |
| `eol_date` | date | YES | - |
| `pricing` | jsonb | YES | '{}'::jsonb |
| `product_type` | character varying(100) | YES | - |
| `confidence` | float8 | YES | 0.0 |
| `source_urls` | _text | YES | - |
| `research_date` | timestamptz | YES | now() |
| `cache_valid_until` | timestamptz | YES | - |
| `verified` | bool | YES | false |
| `verified_by` | character varying(100) | YES | - |
| `verified_at` | timestamptz | YES | - |
| `notes` | text | YES | - |
| `created_at` | timestamptz | YES | now() |
| `updated_at` | timestamptz | YES | now() |

### krai_intelligence.search_analytics

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `search_query` | text | NO | - |
| `search_type` | character varying(50) | YES | - |
| `results_count` | int4 | YES | - |
| `click_through_rate` | numeric | YES | - |
| `user_satisfaction_rating` | int4 | YES | - |
| `search_duration_ms` | int4 | YES | - |
| `result_relevance_scores` | jsonb | YES | - |
| `user_session_id` | character varying(100) | YES | - |
| `user_id` | uuid | YES | - |
| `manufacturer_filter` | uuid | YES | - |
| `product_filter` | uuid | YES | - |
| `document_type_filter` | character varying(100) | YES | - |
| `language_filter` | character varying(10) | YES | - |
| `created_at` | timestamptz | YES | now() |

### krai_intelligence.session_context

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `session_id` | text | NO | - |
| `context_type` | text | NO | - |
| `context_value` | text | NO | - |
| `confidence` | float8 | YES | 1.0 |
| `first_mentioned_at` | timestamptz | YES | now() |
| `last_used_at` | timestamptz | YES | now() |
| `use_count` | int4 | YES | 1 |

### krai_intelligence.structured_tables

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `document_id` | uuid | NO | - |
| `chunk_id` | uuid | YES | - |
| `page_number` | int4 | YES | - |
| `table_index` | int4 | YES | - |
| `table_type` | character varying(50) | YES | - |
| `column_headers` | _text | YES | - |
| `row_count` | int4 | YES | - |
| `column_count` | int4 | YES | - |
| `table_data` | jsonb | YES | - |
| `table_markdown` | text | YES | - |
| `caption` | text | YES | - |
| `context_text` | text | YES | - |
| `related_error_codes` | _text | YES | - |
| `related_products` | _text | YES | - |
| `related_chunks` | _uuid | YES | - |
| `table_embedding` | vector | YES | - |
| `context_embedding` | vector | YES | - |
| `column_embeddings` | jsonb | YES | - |
| `metadata` | jsonb | YES | '{}'::jsonb |
| `created_at` | timestamptz | YES | now() |
| `updated_at` | timestamptz | YES | now() |

### krai_intelligence.tool_usage

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `session_id` | text | NO | - |
| `tool_name` | text | NO | - |
| `query_params` | jsonb | YES | - |
| `results_count` | int4 | YES | - |
| `response_time_ms` | int4 | YES | - |
| `success` | bool | YES | true |
| `error_message` | text | YES | - |
| `created_at` | timestamptz | YES | now() |

### krai_intelligence.user_satisfaction

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `date` | date | YES | - |
| `total_feedback` | int8 | YES | - |
| `avg_rating` | numeric | YES | - |
| `positive_feedback` | int8 | YES | - |
| `negative_feedback` | int8 | YES | - |
| `helpful_count` | int8 | YES | - |
| `not_helpful_count` | int8 | YES | - |
| `incorrect_count` | int8 | YES | - |

## krai_parts

### krai_parts.inventory_levels

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `part_id` | uuid | NO | - |
| `warehouse_location` | character varying(100) | YES | - |
| `current_stock` | int4 | YES | 0 |
| `minimum_stock_level` | int4 | YES | 0 |
| `maximum_stock_level` | int4 | YES | 1000 |
| `last_updated` | timestamptz | YES | now() |

### krai_parts.parts_catalog

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `manufacturer_id` | uuid | NO | - |
| `part_number` | character varying(100) | NO | - |
| `part_name` | character varying(255) | YES | - |
| `part_description` | text | YES | - |
| `part_category` | character varying(100) | YES | - |
| `unit_price_usd` | numeric | YES | - |
| `created_at` | timestamptz | YES | now() |

## krai_system

### krai_system.audit_log

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `table_name` | character varying(100) | NO | - |
| `record_id` | uuid | NO | - |
| `operation` | character varying(10) | NO | - |
| `old_values` | jsonb | YES | - |
| `new_values` | jsonb | YES | - |
| `changed_by` | character varying(100) | YES | - |
| `changed_at` | timestamptz | YES | now() |
| `session_id` | character varying(100) | YES | - |
| `ip_address` | inet | YES | - |
| `user_agent` | text | YES | - |

### krai_system.health_checks

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `service_name` | character varying(100) | NO | - |
| `check_type` | character varying(50) | NO | - |
| `status` | character varying(20) | NO | - |
| `response_time_ms` | int4 | YES | - |
| `error_message` | text | YES | - |
| `details` | jsonb | YES | '{}'::jsonb |
| `checked_at` | timestamptz | YES | now() |

### krai_system.processing_queue

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `document_id` | uuid | YES | - |
| `chunk_id` | uuid | YES | - |
| `image_id` | uuid | YES | - |
| `video_id` | uuid | YES | - |
| `stage` | character varying(50) | NO | 'storage'::character varying |
| `task_type` | character varying(50) | NO | - |
| `priority` | int4 | YES | 5 |
| `status` | character varying(20) | YES | 'pending'::character varying |
| `scheduled_at` | timestamptz | YES | now() |
| `started_at` | timestamptz | YES | - |
| `completed_at` | timestamptz | YES | - |
| `error_message` | text | YES | - |
| `retry_count` | int4 | YES | 0 |
| `max_retries` | int4 | YES | 3 |
| `payload` | jsonb | YES | '{}'::jsonb |
| `created_at` | timestamptz | YES | now() |

### krai_system.stage_tracking

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `document_id` | uuid | YES | - |
| `stage_name` | character varying(100) | NO | - |
| `status` | character varying(50) | NO | - |
| `started_at` | timestamptz | YES | now() |
| `completed_at` | timestamptz | YES | - |
| `error_message` | text | YES | - |
| `metadata` | jsonb | YES | '{}'::jsonb |
| `created_at` | timestamptz | YES | now() |
| `updated_at` | timestamptz | YES | now() |

### krai_system.system_metrics

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | extensions.uuid_generate_v4() |
| `metric_name` | character varying(100) | NO | - |
| `metric_value` | numeric | YES | - |
| `metric_unit` | character varying(20) | YES | - |
| `metric_category` | character varying(50) | YES | - |
| `collection_timestamp` | timestamptz | YES | now() |
| `server_instance` | character varying(100) | YES | - |
| `additional_context` | jsonb | YES | '{}'::jsonb |

### krai_system.stage_completion_markers

**Description:** Tracks stage completion with data hashing for idempotency checks

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `document_id` | uuid | NO | - |
| `stage_name` | character varying(50) | NO | - |
| `completed_at` | timestamp | NO | CURRENT_TIMESTAMP |
| `data_hash` | character varying(64) | YES | - |
| `metadata` | jsonb | YES | - |

**Primary Key:** `(document_id, stage_name)`

### krai_system.pipeline_errors

**Description:** Primary table for error tracking and Dashboard queries

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `error_id` | character varying(100) | NO | - |
| `document_id` | uuid | NO | - |
| `stage_name` | character varying(50) | NO | - |
| `error_type` | character varying(50) | NO | - |
| `error_category` | character varying(50) | NO | - |
| `error_message` | text | NO | - |
| `stack_trace` | text | YES | - |
| `context` | jsonb | YES | - |
| `retry_count` | int4 | NO | 0 |
| `max_retries` | int4 | NO | 3 |
| `next_retry_at` | timestamp | YES | - |
| `status` | character varying(20) | NO | 'pending' |
| `severity` | character varying(20) | NO | 'medium' |
| `is_transient` | bool | NO | true |
| `correlation_id` | character varying(100) | YES | - |
| `parent_error_id` | character varying(100) | YES | - |
| `created_at` | timestamp | NO | CURRENT_TIMESTAMP |
| `updated_at` | timestamp | NO | CURRENT_TIMESTAMP |
| `resolved_at` | timestamp | YES | - |
| `resolved_by` | uuid | YES | - |
| `resolution_notes` | text | YES | - |
| `stage_status` | jsonb | YES | - |
| `error_details` | jsonb | YES | - |

**Unique Constraint:** `error_id`

**Indexes:**
- `idx_pipeline_errors_document_id` on `document_id`
- `idx_pipeline_errors_stage_name` on `stage_name`
- `idx_pipeline_errors_status` on `status`
- `idx_pipeline_errors_severity` on `severity`
- `idx_pipeline_errors_created_at` on `created_at`
- `idx_pipeline_errors_correlation` on `correlation_id`
- `idx_pipeline_errors_resolved_by` on `resolved_by`

### krai_system.alert_queue

**Description:** Queue for alert aggregation to prevent spam

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `alert_type` | character varying(50) | NO | - |
| `severity` | character varying(20) | NO | - |
| `message` | text | NO | - |
| `details` | jsonb | YES | - |
| `aggregation_key` | character varying(200) | YES | - |
| `aggregation_count` | int4 | NO | 1 |
| `first_occurrence` | timestamp | NO | CURRENT_TIMESTAMP |
| `last_occurrence` | timestamp | NO | CURRENT_TIMESTAMP |
| `status` | character varying(20) | NO | 'pending' |
| `sent_at` | timestamp | YES | - |
| `created_at` | timestamp | NO | CURRENT_TIMESTAMP |

### krai_system.alert_configurations

**Description:** Stores alert rules and recipients configured via Dashboard

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `rule_name` | character varying(100) | NO | - |
| `description` | text | YES | - |
| `is_enabled` | bool | NO | true |
| `error_types` | character varying(50)[] | YES | - |
| `stages` | character varying(50)[] | YES | - |
| `severity_threshold` | character varying(20) | NO | 'medium' |
| `error_count_threshold` | int4 | NO | 5 |
| `time_window_minutes` | int4 | NO | 15 |
| `aggregation_window_minutes` | int4 | NO | 5 |
| `email_recipients` | text[] | YES | - |
| `slack_webhooks` | text[] | YES | - |
| `created_by` | uuid | YES | - |
| `created_at` | timestamp | NO | CURRENT_TIMESTAMP |
| `updated_at` | timestamp | NO | CURRENT_TIMESTAMP |

**Unique Constraint:** `rule_name`

### krai_system.retry_policies

**Description:** Configurable retry policies per service/stage

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `policy_name` | character varying(100) | NO | - |
| `service_name` | character varying(50) | NO | - |
| `stage_name` | character varying(50) | YES | - |
| `max_retries` | int4 | NO | 3 |
| `base_delay_seconds` | numeric(5,2) | NO | 1.0 |
| `max_delay_seconds` | numeric(5,2) | NO | 60.0 |
| `exponential_base` | numeric(3,2) | NO | 2.0 |
| `jitter_enabled` | bool | NO | true |
| `circuit_breaker_enabled` | bool | NO | false |
| `circuit_breaker_threshold` | int4 | NO | 5 |
| `circuit_breaker_timeout_seconds` | int4 | NO | 60 |
| `created_at` | timestamp | NO | CURRENT_TIMESTAMP |
| `updated_at` | timestamp | NO | CURRENT_TIMESTAMP |

**Unique Constraint:** `policy_name`

### krai_system.performance_baselines

**Description:** Stores performance baselines and measurements

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `stage_name` | character varying(50) | NO | - |
| `baseline_avg_seconds` | numeric(10,3) | NO | - |
| `baseline_p50_seconds` | numeric(10,3) | NO | - |
| `baseline_p95_seconds` | numeric(10,3) | NO | - |
| `baseline_p99_seconds` | numeric(10,3) | NO | - |
| `current_avg_seconds` | numeric(10,3) | YES | - |
| `current_p50_seconds` | numeric(10,3) | YES | - |
| `current_p95_seconds` | numeric(10,3) | YES | - |
| `current_p99_seconds` | numeric(10,3) | YES | - |
| `improvement_percentage` | numeric(5,2) | YES | - |
| `test_document_ids` | uuid[] | YES | - |
| `measurement_date` | timestamp | NO | CURRENT_TIMESTAMP |
| `notes` | text | YES | - |
| `created_at` | timestamp | NO | CURRENT_TIMESTAMP |

## krai_users

### krai_users.user_sessions

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `user_id` | uuid | NO | - |
| `session_token` | character varying(255) | NO | - |
| `expires_at` | timestamptz | NO | - |
| `created_at` | timestamptz | YES | now() |

### krai_users.users

| Spalte | Typ | Nullable | Default |
|--------|-----|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `preferred_manufacturer_id` | uuid | YES | - |
| `username` | character varying(100) | NO | - |
| `email` | character varying(255) | NO | - |
| `role` | character varying(50) | NO | 'user'::character varying |
| `password_hash` | character varying(255) | NO | repeat('0'::text, 60) |
| `first_name` | character varying(100) | YES | - |
| `last_name` | character varying(100) | YES | - |
| `status` | character varying(50) | NO | 'active'::character varying |
| `is_active` | bool | NO | true |
| `is_verified` | bool | NO | false |
| `permissions` | jsonb | NO | '{}'::jsonb |
| `last_login` | timestamptz | YES | - |
| `login_count` | int4 | NO | 0 |
| `failed_login_attempts` | int4 | NO | 0 |
| `locked_until` | timestamptz | YES | - |
| `updated_at` | timestamptz | NO | now() |
| `profile_image_url` | text | YES | - |
| `created_at` | timestamptz | YES | now() |

---

## Public Views (vw_*)

Alle Views nutzen `vw_` Prefix und zeigen auf Tabellen in krai_* Schemas:

| View | Zeigt auf | Hinweis |
|------|-----------|---------|
| `vw_agent_memory` | `krai_agent.memory` | - |
| `vw_audit_log` | `krai_system.audit_log` | - |
| `vw_chunks` | `krai_intelligence.chunks` | ⚠️ Enthält embedding Spalte! |
| `vw_document_products` | `krai_core.document_products` | - |
| `vw_documents` | `krai_core.documents` | - |
| `vw_embeddings` | `ALIAS für vw_chunks` | ⚠️ Embeddings sind IN chunks! |
| `vw_error_codes` | `krai_intelligence.error_codes` | - |
| `vw_images` | `krai_content.images` | - |
| `vw_intelligence_chunks` | `krai_intelligence.chunks` | - |
| `vw_links` | `krai_content.links` | - |
| `vw_manufacturers` | `krai_core.manufacturers` | - |
| `vw_parts` | `krai_parts.parts_catalog` | - |
| `vw_processing_queue` | `krai_system.processing_queue` | - |
| `vw_product_series` | `krai_core.product_series` | - |
| `vw_products` | `krai_core.products` | - |
| `vw_search_analytics` | `krai_intelligence.search_analytics` | - |
| `vw_system_metrics` | `krai_system.system_metrics` | - |
| `vw_video_products` | `krai_content.video_products` | - |
| `vw_videos` | `krai_content.videos` | - |
| `vw_webhook_logs` | `krai_integrations.webhook_logs` | - |

---

## Table Relationships

| From Table | To Table | Relationship | Purpose |
|------------|----------|--------------|---------|
| `pipeline_errors` | `krai_core.documents` | Many-to-One (FK: document_id) | Track errors per document |
| `pipeline_errors` | `krai_users.users` | Many-to-One (FK: resolved_by) | Track who resolves errors |
| `alert_queue` | `alert_configurations` | Logical (via aggregation_key) | Match alerts to rules through aggregation_key pattern matching |
| `alert_configurations` | `krai_users.users` | Many-to-One (FK: created_by) | Track rule creators |
| `stage_completion_markers` | `krai_core.documents` | Many-to-One (implicit) | Track stage completion per document |
| `retry_policies` | N/A | Standalone | Service configuration |
| `performance_baselines` | N/A | Standalone | Performance tracking |

---

## Statistik

- **Schemas:** 6
- **Tabellen:** 44
- **Spalten:** 604
