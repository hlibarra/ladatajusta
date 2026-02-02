-- Migration 012: Add auto_publish fields to scraping_sources
-- Enables automatic publication of ready_to_publish items after a configurable delay

-- Add auto_publish flag (default false for safety)
ALTER TABLE scraping_sources
ADD COLUMN IF NOT EXISTS auto_publish BOOLEAN NOT NULL DEFAULT FALSE;

-- Add configurable delay in minutes (default 15 minutes)
ALTER TABLE scraping_sources
ADD COLUMN IF NOT EXISTS auto_publish_delay_minutes INTEGER NOT NULL DEFAULT 15;

-- Add index for efficient querying of auto-publish enabled sources
CREATE INDEX IF NOT EXISTS idx_scraping_sources_auto_publish
ON scraping_sources (auto_publish) WHERE auto_publish = TRUE;

-- Add comment for documentation
COMMENT ON COLUMN scraping_sources.auto_publish IS
'When true, items from this source will be auto-published after passing quality checks and delay period';

COMMENT ON COLUMN scraping_sources.auto_publish_delay_minutes IS
'Minutes to wait after item becomes ready_to_publish before auto-publishing (allows admin review window)';
