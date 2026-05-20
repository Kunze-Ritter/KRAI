-- Migration 022: Add index on krai_intelligence.chunks.fingerprint
-- Improves upsert performance (ON CONFLICT + dedup lookups)

CREATE INDEX IF NOT EXISTS idx_chunks_fingerprint
    ON krai_intelligence.chunks (fingerprint);

INSERT INTO krai_system.migrations (migration_name, applied_at, description)
VALUES ('022_chunks_fingerprint_index', NOW(),
        'Index on krai_intelligence.chunks.fingerprint for fast deduplication')
ON CONFLICT (migration_name) DO NOTHING;
