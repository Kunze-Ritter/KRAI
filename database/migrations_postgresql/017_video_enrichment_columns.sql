-- Add missing columns for video enrichment
ALTER TABLE krai_content.videos
ADD COLUMN IF NOT EXISTS tags TEXT[],
ADD COLUMN IF NOT EXISTS enrichment_error TEXT;

-- Remove unused column from duplicate migration variant, if present
ALTER TABLE krai_content.videos
DROP COLUMN IF EXISTS duration_seconds;

-- Replace old narrow index with pending-enrichment index used by processor filters
DROP INDEX IF EXISTS idx_videos_needs_enrichment;
CREATE INDEX IF NOT EXISTS idx_videos_enrichment_pending
ON krai_content.videos (platform)
WHERE platform = 'brightcove'
  AND (
    COALESCE((metadata->>'needs_enrichment')::boolean, false) = true
    OR COALESCE(BTRIM(title), '') = ''
    OR COALESCE(BTRIM(context_description), '') = ''
  );

-- Add comment
COMMENT ON COLUMN krai_content.videos.tags IS 'Video tags/keywords from platform metadata';
COMMENT ON COLUMN krai_content.videos.enrichment_error IS 'Error message if enrichment failed';

-- Record migration
INSERT INTO krai_system.migrations (migration_name, applied_at, description)
VALUES ('017_video_enrichment_columns', NOW(), 'Add tags and enrichment_error columns for Brightcove video enrichment')
ON CONFLICT (migration_name) DO NOTHING;
