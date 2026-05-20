-- Migration 007: Fix Firecrawl NUQ schema drift (Firecrawl :latest)
-- Align nuq.* tables with Firecrawl's Postgres-based NUQ implementation

-- Ensure required extension for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Ensure nuq schema exists
CREATE SCHEMA IF NOT EXISTS nuq;

-- =====================================================
-- Types
-- =====================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'nuq' AND t.typname = 'job_status'
    ) THEN
        CREATE TYPE nuq.job_status AS ENUM ('queued', 'active', 'completed', 'failed');
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'nuq' AND t.typname = 'group_status'
    ) THEN
        CREATE TYPE nuq.group_status AS ENUM ('active', 'completed', 'failed', 'pending');
    END IF;
END $$;

-- =====================================================
-- group_crawl (used by NuQJobGroup)
-- =====================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'nuq' AND table_name = 'group_crawl'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'nuq' AND table_name = 'group_crawl_legacy'
    ) THEN
        ALTER TABLE nuq.group_crawl RENAME TO group_crawl_legacy;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS nuq.group_crawl (
    id uuid PRIMARY KEY,
    status nuq.group_status NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    owner_id uuid,
    ttl bigint NOT NULL DEFAULT 86400000,
    expires_at timestamptz
);

-- =====================================================
-- Base NUQ tables (create if missing)
-- =====================================================
CREATE TABLE IF NOT EXISTS nuq.queue_scrape (
    id uuid PRIMARY KEY,
    status nuq.job_status NOT NULL DEFAULT 'queued',
    created_at timestamptz NOT NULL DEFAULT now(),
    priority integer NOT NULL DEFAULT 0,
    data jsonb NOT NULL DEFAULT '{}'::jsonb,
    finished_at timestamptz,
    listen_channel_id text,
    returnvalue jsonb,
    failedreason text,
    lock uuid,
    locked_at timestamptz,
    owner_id uuid,
    group_id uuid
);

CREATE TABLE IF NOT EXISTS nuq.queue_crawl (
    id uuid PRIMARY KEY,
    status nuq.job_status NOT NULL DEFAULT 'queued',
    created_at timestamptz NOT NULL DEFAULT now(),
    priority integer NOT NULL DEFAULT 0,
    data jsonb NOT NULL DEFAULT '{}'::jsonb,
    finished_at timestamptz,
    listen_channel_id text,
    returnvalue jsonb,
    failedreason text,
    lock uuid,
    locked_at timestamptz,
    owner_id uuid,
    group_id uuid
);

CREATE TABLE IF NOT EXISTS nuq.queue_map (
    id uuid PRIMARY KEY,
    status nuq.job_status NOT NULL DEFAULT 'queued',
    created_at timestamptz NOT NULL DEFAULT now(),
    priority integer NOT NULL DEFAULT 0,
    data jsonb NOT NULL DEFAULT '{}'::jsonb,
    finished_at timestamptz,
    listen_channel_id text,
    returnvalue jsonb,
    failedreason text,
    lock uuid,
    locked_at timestamptz,
    owner_id uuid,
    group_id uuid
);

-- =====================================================
-- queue_scrape
-- =====================================================
-- Ensure columns needed by Firecrawl exist
ALTER TABLE nuq.queue_scrape
    ADD COLUMN IF NOT EXISTS locked_at timestamptz;

-- Normalize status values before converting type
UPDATE nuq.queue_scrape
SET status = (CASE
    WHEN status IS NULL THEN 'queued'
    WHEN status::text IN ('pending', 'queued') THEN 'queued'
    WHEN status::text IN ('processing', 'active') THEN 'active'
    WHEN status::text = 'completed' THEN 'completed'
    WHEN status::text = 'failed' THEN 'failed'
    ELSE 'queued'
END)::nuq.job_status;

-- Drop default before enum conversion (Postgres cannot auto-cast existing default)
ALTER TABLE nuq.queue_scrape
    ALTER COLUMN status DROP DEFAULT;

-- Convert columns to types expected by Firecrawl NUQ
ALTER TABLE nuq.queue_scrape
    ALTER COLUMN id TYPE uuid USING NULLIF(id::text, '')::uuid,
    ALTER COLUMN status TYPE nuq.job_status USING status::text::nuq.job_status,
    ALTER COLUMN lock TYPE uuid USING NULLIF(lock::text, '')::uuid,
    ALTER COLUMN owner_id TYPE uuid USING NULLIF(owner_id::text, '')::uuid,
    ALTER COLUMN group_id TYPE uuid USING NULLIF(group_id::text, '')::uuid;

ALTER TABLE nuq.queue_scrape
    ALTER COLUMN status SET DEFAULT 'queued';

-- =====================================================
-- queue_crawl + queue_map (keep compatible)
-- =====================================================
ALTER TABLE nuq.queue_crawl
    ADD COLUMN IF NOT EXISTS locked_at timestamptz;

UPDATE nuq.queue_crawl
SET status = (CASE
    WHEN status IS NULL THEN 'queued'
    WHEN status::text IN ('pending', 'queued') THEN 'queued'
    WHEN status::text IN ('processing', 'active') THEN 'active'
    WHEN status::text = 'completed' THEN 'completed'
    WHEN status::text = 'failed' THEN 'failed'
    ELSE 'queued'
END)::nuq.job_status;

ALTER TABLE nuq.queue_crawl
    ALTER COLUMN status DROP DEFAULT;

ALTER TABLE nuq.queue_crawl
    ALTER COLUMN id TYPE uuid USING NULLIF(id::text, '')::uuid,
    ALTER COLUMN status TYPE nuq.job_status USING status::text::nuq.job_status,
    ALTER COLUMN lock TYPE uuid USING NULLIF(lock::text, '')::uuid,
    ALTER COLUMN owner_id TYPE uuid USING NULLIF(owner_id::text, '')::uuid,
    ALTER COLUMN group_id TYPE uuid USING NULLIF(group_id::text, '')::uuid;

ALTER TABLE nuq.queue_crawl
    ALTER COLUMN status SET DEFAULT 'queued';

ALTER TABLE nuq.queue_map
    ADD COLUMN IF NOT EXISTS locked_at timestamptz;

UPDATE nuq.queue_map
SET status = (CASE
    WHEN status IS NULL THEN 'queued'
    WHEN status::text IN ('pending', 'queued') THEN 'queued'
    WHEN status::text IN ('processing', 'active') THEN 'active'
    WHEN status::text = 'completed' THEN 'completed'
    WHEN status::text = 'failed' THEN 'failed'
    ELSE 'queued'
END)::nuq.job_status;

ALTER TABLE nuq.queue_map
    ALTER COLUMN status DROP DEFAULT;

ALTER TABLE nuq.queue_map
    ALTER COLUMN id TYPE uuid USING NULLIF(id::text, '')::uuid,
    ALTER COLUMN status TYPE nuq.job_status USING status::text::nuq.job_status,
    ALTER COLUMN lock TYPE uuid USING NULLIF(lock::text, '')::uuid,
    ALTER COLUMN owner_id TYPE uuid USING NULLIF(owner_id::text, '')::uuid,
    ALTER COLUMN group_id TYPE uuid USING NULLIF(group_id::text, '')::uuid;

ALTER TABLE nuq.queue_map
    ALTER COLUMN status SET DEFAULT 'queued';

-- =====================================================
-- backlog table for scrape queue (NuQ backlog support)
-- =====================================================
CREATE TABLE IF NOT EXISTS nuq.queue_scrape_backlog (
    id uuid PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    priority integer NOT NULL DEFAULT 0,
    data jsonb NOT NULL DEFAULT '{}'::jsonb,
    listen_channel_id text,
    owner_id uuid,
    group_id uuid,
    times_out_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_queue_scrape_backlog_times_out_at
    ON nuq.queue_scrape_backlog(times_out_at);

-- =====================================================
-- crawl finished queue (used by nuq-prefetch-worker)
-- =====================================================
CREATE TABLE IF NOT EXISTS nuq.queue_crawl_finished (
    id uuid PRIMARY KEY,
    status nuq.job_status NOT NULL DEFAULT 'queued',
    created_at timestamptz NOT NULL DEFAULT now(),
    priority integer NOT NULL DEFAULT 0,
    data jsonb NOT NULL DEFAULT '{}'::jsonb,
    finished_at timestamptz,
    listen_channel_id text,
    returnvalue jsonb,
    failedreason text,
    lock uuid,
    locked_at timestamptz,
    owner_id uuid,
    group_id uuid
);

-- Permissions
GRANT USAGE ON SCHEMA nuq TO krai_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA nuq TO krai_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA nuq TO krai_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA nuq TO krai_user;
