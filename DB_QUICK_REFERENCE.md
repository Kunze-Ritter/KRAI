# KRAI Database Quick Reference
================================================================================
**Letzte Aktualisierung:** 20.05.2026 um 11:49 UTC
**Live-DB:** `krai` | **Fingerprint:** `98c8bb67f30dd682`

> ⚠️ **WICHTIG**: Vor jedem DB-Zugriff diese Referenz + `schema/krai.dbml` prüfen!
> Regenerieren: `python scripts/generate_schema_docs.py`

## Schemas (8)

| Schema | Tabellen | Zweck |
|--------|----------|-------|
| `krai_content` | 7 | Media — images, videos, links, print_defects |
| `krai_core` | 10 | Business-Entitäten — documents, products, manufacturers, series |
| `krai_intelligence` | 6 | AI/ML — chunks, embeddings, error_codes, solutions |
| `krai_parts` | 2 | Ersatzteile — parts_catalog, accessories |
| `krai_pm` | 11 | Project Management (eigenes Schema) |
| `krai_system` | 20 | Pipeline, Queue, Alerts, Metrics, Migrations, Stage-Tracking |
| `krai_users` | 5 | Benutzer und Sessions |
| `public` | 3 | — |

## Kritische Tabellen

| Tabelle | Zweck | embedding |
|---------|-------|-----------|
| `krai_intelligence.chunks` | Text-Chunks | ✅ `embedding vector(768)` |
| `krai_core.documents` | Hauptdokumente | ❌ |
| `krai_content.videos` | Videos | ❌ (metadata JSONB) |
| `krai_content.links` | Links | ❌ |
| `krai_content.images` | Bilder | ❌ |
| `krai_intelligence.error_codes` | Fehlercodes | ❌ |
| `krai_system.processing_queue` | Pipeline-Queue | ❌ |

## Views (vw_*)

- `public.vw_device_lifecycle`
- `public.vw_part_lifetimes`
- `public.vw_predictions`

> ⚠️ Embeddings liegen in krai_intelligence.chunks.embedding — nicht in Views suchen.

## Known Traps ❌→✅

| Falsch | Richtig | Tabelle |
|--------|---------|---------|
| `chunk_text` | `text_chunk` | `krai_intelligence.chunks` |
| `enrichment_error` | `metadata->>'enrichment_error'` | `krai_content.videos` |
| `tags` | `metadata->>'tags'` | `krai_content.videos` |
| `solution_text` | `solution_technician_text` | `krai_intelligence.error_codes` |
| `requires_technician` | `(entfernt)` | `krai_intelligence.error_codes` |
| `Error-Code Großbuchstaben` | `error_code (Kleinbuchstaben)` | `krai_intelligence.error_codes` |

## Extensions

```sql
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "unaccent";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
```

## Pipeline Stages → DB

| Stage | Tabelle/View |
|-------|--------------|
| UPLOAD | `krai_core.documents` |
| TEXT_EXTRACTION | `krai_intelligence.chunks` |
| IMAGE_PROCESSING | `krai_content.images` |
| CLASSIFICATION | `krai_core.products, krai_core.manufacturers` |
| METADATA_EXTRACTION | `krai_intelligence.error_codes` |
| PARTS_EXTRACTION | `krai_parts.parts_catalog` |
| STORAGE | `MinIO (nicht in DB)` |
| EMBEDDING | `krai_intelligence.chunks.embedding` |
| SEARCH_INDEXING | `krai_analytics.search_analytics` |

## Nützliche Queries

```sql
-- Dokumente in Pipeline
SELECT id, status, current_stage FROM krai_system.processing_queue;

-- Chunks ohne Embedding
SELECT id, text_chunk FROM krai_intelligence.chunks WHERE embedding IS NULL;

-- Error Codes mit Hierarchy
SELECT error_code, parent_code, is_category FROM krai_intelligence.error_codes
WHERE parent_code IS NOT NULL ORDER BY parent_code, error_code;
```

## Vollständige Referenz

- [`DATABASE_SCHEMA.md`](../DATABASE_SCHEMA.md) — alle Spalten
- [`schema/krai.dbml`](../schema/krai.dbml) — ERD für dbdiagram.io
