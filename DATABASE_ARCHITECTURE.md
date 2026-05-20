# KRAI Database Architecture

**Purpose:** the *semantic* layer of the database — what each schema is **for**, who
**writes** to it, what is **canonical** when names overlap, and what is **deprecated**.
This complements the auto-generated structural docs and exists to stop the
"queried the wrong table / assumed a dead schema" class of bugs.

**Source of truth:** live PostgreSQL (`krai` on Docker `krai-postgres-prod`).
**Generated:** 2026-05-20 · **Schema fingerprint:** `98c8bb67f30dd682`

> Structural reference (columns/FKs/types) is **auto-generated** — do not hand-edit:
> - `DATABASE_SCHEMA.md` — full column reference
> - `DB_QUICK_REFERENCE.md` — compact reference + traps
> - `schema/krai.dbml` — ERD (dbdiagram.io)
> - Regenerate after every schema change: `python scripts/generate_schema_docs.py`
>   and verify with `--check` (wired into pre-commit).

---

## Schema map (7 active `krai_*` schemas + `public`)

| Schema | Size | Purpose | Primary writer(s) | Lifecycle |
|--------|------|---------|-------------------|-----------|
| `krai_intelligence` | 3.2 GB | The "brain": chunks, embeddings, extracted tables, error codes | EmbeddingProcessor, ChunkPreprocessor, TableProcessor, ErrorCodeExtractor | active |
| `krai_system` | 722 MB | Pipeline operations: queue, stage tracking/metrics, errors, alerts, retry, prompts, **backend migration tracker** | MasterPipeline, IdempotencyChecker, AlertService, run_migrations.py | active |
| `krai_content` | 42 MB | Media artifacts: images, videos, video↔product links, external links | ImageProcessor, VideoEnrichmentProcessor, LinkExtractionProcessor | active |
| `krai_pm` | 12 MB | Predictive maintenance: service tickets, part lifetimes, warranty events, predictions | `backend/pm/*` (Radix importer, WarrantyTracker, prediction service) | active (in development) |
| `krai_core` | <1 MB | Source-of-truth entities: documents, products, series, manufacturers | UploadProcessor, MetadataProcessor, SeriesProcessor | active — **protected** |
| `krai_users` | <1 MB | Auth & chat: users, sessions, chat history, token blacklist | AuthService, chat API | active |
| `krai_parts` | <1 MB | Parts catalog & inventory | PartsProcessor | active |
| `public` | — | **Laravel's** `migrations` table (laravel-admin dashboard) — NOT the backend's | Laravel/Filament | active (separate system) |

### Key tables by schema (rows as of generation)

- **krai_intelligence**: `unified_embeddings` (430,587 — multimodal embedding store),
  `structured_tables` (22,286), `chunks` (20,943 — **canonical** text chunks, has
  `embedding` column), `error_codes` (2,937), `search_analytics`, `manufacturer_verification_cache`.
- **krai_system**: `stage_completion_markers` (607 — idempotency), `processing_queue`
  (378), `stage_metrics`/`stage_tracking`, `migrations` (43 — backend SQL migrations),
  `pipeline_errors`, `retry_policies`, `prompt_templates`, `alerts`, …
- **krai_content**: `images` (7,431), `video_products` (7,274), `videos` (6,677),
  `links` (260). *(`krai_content.chunks` was a dead duplicate — dropped in migration 040.)*
- **krai_pm**: `service_tickets` (7,045 — real Radix data), `part_lifetimes` (126),
  `part_warranty_events`/`predictions`/`device_lifecycle`/`entity_mapping`/`service_routes`
  (built, **not yet populated** — see backlog).
- **krai_core**: `products` (385), `document_products` (50), `product_series` (11),
  `manufacturers` (10), `documents` (9). **9 documents generate the 430k+ embeddings.**
- **krai_parts**: `parts_catalog` (523). **krai_users**: `users` (2), chat tables.

---

## Canonical sources (resolved duplicates)

| Concept | ✅ Canonical | ❌ Removed / forbidden |
|---------|-------------|------------------------|
| Text chunks | `krai_intelligence.chunks` (`text_chunk`, `embedding`) | `krai_content.chunks` — **dropped** (migration 040) |
| Search analytics | `krai_intelligence.search_analytics` | `krai_analytics.search_analytics` — **dropped** |
| Backend SQL migrations | `krai_system.migrations` (`migration_name`, `applied_at`) | — |
| Laravel migrations | `public.migrations` (`id`, `migration`, `batch`) | — (different system; leave alone) |

**Column traps** (historically caused bugs — use the right name):
`text_chunk` not `chunk_text` (chunks); video `tags`/`enrichment_error` live in
`metadata` JSONB, not columns. See `schema/column-traps.yaml`.

---

## Migration process

Backend SQL migrations live in `database/migrations_postgresql/NNN_*.sql` and are
**version-controlled** (a blanket `*.sql` gitignore previously hid them — fixed).

```bash
python scripts/run_migrations.py --status     # applied vs pending
python scripts/run_migrations.py              # apply pending (each in a transaction)
python scripts/run_migrations.py --baseline   # record on-disk migrations as applied
```

Applied migrations are recorded in `krai_system.migrations`. After any schema change:
regenerate docs (`generate_schema_docs.py`) and commit the generated files with the
migration.

---

## Removed in consolidation (migration 040, 2026-05-20)

Dropped 5 entirely-empty, unreferenced schemas: `krai_analytics`, `krai_config`,
`krai_integrations`, `krai_ml`, `krai_service` (the last superseded by `krai_pm`).
Plus `krai_content.chunks` (empty duplicate). DB went 12 → 7 `krai_*` schemas,
71 → 54 foreign keys.

## Known optimization debt (not yet actioned)

- **Embedding storage overlap (~P0):** `krai_intelligence.chunks.embedding` (text) and
  `unified_embeddings` (`source_type='text'`) hold overlapping text embeddings; the 3.2 GB
  is dominated by `unified_embeddings`. Needs a dedup strategy + ADR.
- **`processing_queue` bloat:** 722 MB across 378 rows (oversized JSONB payloads). Needs
  payload slimming + retention.

## Protected data (never lose)

`krai_core.manufacturers`, `krai_core.products`, `krai_core.product_series`,
`krai_content.videos`, `krai_content.video_products`. Seed backup:
`backups/seed_<date>.sql` (excluded from git).
