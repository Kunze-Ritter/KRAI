-- =====================================================
-- Firecrawl Queue Tables Migration
-- =====================================================
-- Creates the necessary tables for Firecrawl's NUQ (Not Unique Queue) system
-- Based on Firecrawl's database schema requirements

-- Create nuq schema if it doesn't exist (should already exist)
CREATE SCHEMA IF NOT EXISTS nuq;

-- Grant permissions
GRANT USAGE ON SCHEMA nuq TO krai_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA nuq TO krai_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA nuq TO krai_user;

-- =====================================================
-- Queue Scrape Table
-- =====================================================
-- Main table for managing scrape jobs in the queue
CREATE TABLE IF NOT EXISTS nuq.queue_scrape (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL UNIQUE,
    team_id VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    scrape_options JSONB DEFAULT '{}'::jsonb,
    formats JSONB DEFAULT '["markdown"]'::jsonb,
    status VARCHAR(50) DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    error_message TEXT,
    result JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_queue_scrape_job_id ON nuq.queue_scrape(job_id);
CREATE INDEX IF NOT EXISTS idx_queue_scrape_team_id ON nuq.queue_scrape(team_id);
CREATE INDEX IF NOT EXISTS idx_queue_scrape_status ON nuq.queue_scrape(status);
CREATE INDEX IF NOT EXISTS idx_queue_scrape_created_at ON nuq.queue_scrape(created_at);
CREATE INDEX IF NOT EXISTS idx_queue_scrape_priority ON nuq.queue_scrape(priority DESC);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_queue_scrape_status_priority ON nuq.queue_scrape(status, priority DESC);

-- =====================================================
-- Queue Crawl Table
-- =====================================================
-- Table for managing crawl jobs (multi-page scraping)
CREATE TABLE IF NOT EXISTS nuq.queue_crawl (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL UNIQUE,
    team_id VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    crawl_options JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(50) DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    error_message TEXT,
    result JSONB,
    pages_scraped INTEGER DEFAULT 0,
    pages_total INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for crawl queue
CREATE INDEX IF NOT EXISTS idx_queue_crawl_job_id ON nuq.queue_crawl(job_id);
CREATE INDEX IF NOT EXISTS idx_queue_crawl_team_id ON nuq.queue_crawl(team_id);
CREATE INDEX IF NOT EXISTS idx_queue_crawl_status ON nuq.queue_crawl(status);
CREATE INDEX IF NOT EXISTS idx_queue_crawl_created_at ON nuq.queue_crawl(created_at);

-- =====================================================
-- Queue Map Table
-- =====================================================
-- Table for URL mapping jobs
CREATE TABLE IF NOT EXISTS nuq.queue_map (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL UNIQUE,
    team_id VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    map_options JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(50) DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    error_message TEXT,
    result JSONB,
    urls_found INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for map queue
CREATE INDEX IF NOT EXISTS idx_queue_map_job_id ON nuq.queue_map(job_id);
CREATE INDEX IF NOT EXISTS idx_queue_map_team_id ON nuq.queue_map(team_id);
CREATE INDEX IF NOT EXISTS idx_queue_map_status ON nuq.queue_map(status);

-- =====================================================
-- Update Trigger
-- =====================================================
-- Automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION nuq.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to all queue tables
DROP TRIGGER IF EXISTS update_queue_scrape_updated_at ON nuq.queue_scrape;
CREATE TRIGGER update_queue_scrape_updated_at
    BEFORE UPDATE ON nuq.queue_scrape
    FOR EACH ROW
    EXECUTE FUNCTION nuq.update_updated_at_column();

DROP TRIGGER IF EXISTS update_queue_crawl_updated_at ON nuq.queue_crawl;
CREATE TRIGGER update_queue_crawl_updated_at
    BEFORE UPDATE ON nuq.queue_crawl
    FOR EACH ROW
    EXECUTE FUNCTION nuq.update_updated_at_column();

DROP TRIGGER IF EXISTS update_queue_map_updated_at ON nuq.queue_map;
CREATE TRIGGER update_queue_map_updated_at
    BEFORE UPDATE ON nuq.queue_map
    FOR EACH ROW
    EXECUTE FUNCTION nuq.update_updated_at_column();

-- =====================================================
-- Comments
-- =====================================================
COMMENT ON SCHEMA nuq IS 'Firecrawl Not Unique Queue (NUQ) system for managing scraping jobs';
COMMENT ON TABLE nuq.queue_scrape IS 'Queue for single-page scraping jobs';
COMMENT ON TABLE nuq.queue_crawl IS 'Queue for multi-page crawling jobs';
COMMENT ON TABLE nuq.queue_map IS 'Queue for URL mapping/discovery jobs';

COMMENT ON COLUMN nuq.queue_scrape.job_id IS 'Unique identifier for the scrape job';
COMMENT ON COLUMN nuq.queue_scrape.team_id IS 'Team/tenant identifier for multi-tenancy';
COMMENT ON COLUMN nuq.queue_scrape.scrape_options IS 'JSON configuration for scraping behavior';
COMMENT ON COLUMN nuq.queue_scrape.formats IS 'Output formats requested (markdown, html, etc.)';
COMMENT ON COLUMN nuq.queue_scrape.status IS 'Job status: pending, processing, completed, failed';
COMMENT ON COLUMN nuq.queue_scrape.priority IS 'Job priority (higher = processed first)';
COMMENT ON COLUMN nuq.queue_scrape.result IS 'Scraping result data in JSON format';

-- Grant final permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA nuq TO krai_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA nuq TO krai_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA nuq TO krai_user;
