# KRAI Database Quick Reference
================================================================================
**Letzte Aktualisierung:** 05.03.2026

> ⚠️ **WICHTIG**: Vor jedem DB-Zugriff → Diese Referenz prüfen!

## Schemas (7)

| Schema | Zweck |
|--------|-------|
| `krai_core` | Business-Entitäten: manufacturers, products, documents |
| `krai_intelligence` | AI/ML: chunks, embeddings, error_codes |
| `krai_content` | Media: images, videos, links |
| `krai_system` | System: queue, alerts, metrics, audit |
| `krai_parts` | Parts: parts_catalog, accessories |
| `krai_users` | User: users, sessions |
| `krai_analytics` | Analytics: search_analytics |

## Kritische Tabellen

| Tabelle | Zweck | embedding |
|---------|-------|-----------|
| `krai_intelligence.chunks` | Text-Chunks | ✅ Ja (`embedding vector(768)`) |
| `krai_core.documents` | Hauptdokumente | ❌ |
| `krai_content.videos` | Videos | ❌ (metadata JSONB) |
| `krai_content.links` | Links | ❌ |
| `krai_content.images` | Bilder | ❌ |
| `krai_intelligence.error_codes` | Fehlercodes | ❌ |
| `krai_system.processing_queue` | Pipeline-Queue | ❌ |

## Views (vw_*)

> ⚠️ **ACHTUNG**: `vw_embeddings` ist ein Alias für `vw_chunks`!
> Die Embeddings liegen in `krai_intelligence.chunks.embedding`!

## Known Traps ❌→✅

| Falsch | Richtig |
|--------|---------|
| `SELECT chunk_text` | `SELECT text_chunk` |
| `v.enrichment_error` | `v.metadata->>'enrichment_error'` |
| `v.tags` | `v.metadata->>'tags'` |
| Error Code Grossbuchstaben | Kleinbuchstaben! |

## Extensions

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "unaccent";
```

## Pipeline Stages → DB

| Stage | Tabelle/View |
|-------|--------------|
| UPLOAD | `krai_core.documents` |
| TEXT_EXTRACTION | `krai_intelligence.chunks` |
| IMAGE_PROCESSING | `krai_content.images` |
| CLASSIFICATION | `krai_core.products`, `manufacturers` |
| METADATA_EXTRACTION | `krai_intelligence.error_codes` |
| PARTS_EXTRACTION | `krai_parts.parts_catalog` |
| STORAGE | MinIO (nicht in DB) |
| EMBEDDING | `krai_intelligence.chunks.embedding` |
| SEARCH_INDEXING | `krai_intelligence.search_analytics` |

## Nützliche Queries

```sql
-- Dokumente in Pipeline
SELECT id, status, current_stage FROM krai_system.processing_queue;

-- Chunks ohne Embedding (für Nachholen)
SELECT id, text_chunk FROM krai_intelligence.chunks WHERE embedding IS NULL;

-- Error Codes mit Hierarchy
SELECT error_code, parent_code, is_category FROM krai_intelligence.error_codes
WHERE parent_code IS NOT NULL ORDER BY parent_code, error_code;
```
