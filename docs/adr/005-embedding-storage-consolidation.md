# ADR-005: Embedding Storage Consolidation

**Status:** Proposed
**Date:** 2026-05-20
**Context owner:** DB / search pipeline

## Context

The database is ~4.1 GB, of which **`krai_intelligence` is 3.2 GB (79%)**, dominated by
`unified_embeddings` (3.0 GB). Text embeddings are currently stored **twice**:

| Store | Rows | Read by |
|-------|------|---------|
| `krai_intelligence.chunks.embedding` (column) | 16,039 chunks | match functions from migration 029 (`FROM krai_intelligence.chunks c`) |
| `krai_intelligence.unified_embeddings` (`source_type='text'`) | 114,749 (incl. all 16,039 chunk vectors) | `match_multimodal` → `MultimodalSearchService` (primary search) |

**Verified overlap:** all **16,039** chunks that have a column embedding *also* have a
matching `unified_embeddings` row (`source_id = chunk.id`, `source_type='text'`).
`EmbeddingProcessor` writes **both** on every embedding. `unified_embeddings` also holds
`context` (206,413) and `table` (109,209) embeddings — the multimodal store.

So there are **two parallel text-search paths** fed by duplicated data:
- `MultimodalSearchService.match_multimodal` → `unified_embeddings` (text/image/table/context)
- legacy match functions → `chunks.embedding`

## Decision (proposed)

**Make `unified_embeddings` the single source for similarity search; stop duplicating
text embeddings into `chunks.embedding`.**

`unified_embeddings` is the broader, actively-used store (it backs the multimodal
search, the product direction). Keeping `chunks.embedding` only duplicates text vectors
and forces dual writes.

### Options considered

| Option | Description | Pro | Con |
|--------|-------------|-----|-----|
| **A (chosen)** | `unified_embeddings` canonical; migrate the chunk-based match functions to read `unified_embeddings(text)`; stop writing `chunks.embedding`; drop the column after a cutover | Single search API; removes dual writes; reclaims storage | Must migrate match functions + verify search parity |
| B | Keep `chunks.embedding` for text, `unified_embeddings` only for image/table/context | Clear separation | Two code paths for text vs multimodal; ongoing divergence risk |
| C | Replace `chunks.embedding` with a view over `unified_embeddings` | No physical duplication | View/vector-index performance needs validation |

## Migration plan (deliberate, tested — NOT yet executed)

1. Repoint the migration-029 match functions to `unified_embeddings WHERE source_type='text'`.
2. Update `EmbeddingProcessor` to write only `unified_embeddings` for text.
3. Verify search parity (same top-k results) on a sample of queries before/after.
4. Migration: `ALTER TABLE krai_intelligence.chunks DROP COLUMN embedding;` (after cutover).
5. `VACUUM (FULL, ANALYZE)` / `REINDEX` on affected tables to actually reclaim space.
6. Regenerate schema docs.

**Risk:** touches the live search read path — must be done with parity verification,
not blind deletion. This is why it is split out as its own ADR + change, separate from
the structural cleanup already shipped.

## Companion item — `processing_queue` bloat (lower risk)

`krai_system.processing_queue` is **722 MB across 378 rows** (oversized JSONB payloads,
historically all `pending`). Independent of the embedding decision:
- Define a payload contract (references + small metadata; large blobs → MinIO).
- Add retention for completed/stale jobs; `VACUUM (ANALYZE)` after cleanup.

## Consequences

- After A: one embedding store, one search path, no dual writes; meaningful storage
  reclaim once `chunks.embedding` is dropped and tables are vacuumed.
- Until executed, the duplication is documented (here and in `DATABASE_ARCHITECTURE.md`
  → "known optimization debt") so no one assumes `chunks.embedding` is canonical.
