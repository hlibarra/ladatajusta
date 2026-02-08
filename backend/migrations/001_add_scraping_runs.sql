-- Migration: Add scraping_runs table
-- Created: 2026-02-06
-- Description: Creates scraping_runs table to track scraping execution history
-- and adds FK constraint to scraping_items.scraping_run_id

BEGIN;

-- Create scraping_runs table
CREATE TABLE IF NOT EXISTS scraping_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Execution metadata
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,

    -- Status: running, completed, failed, cancelled
    status VARCHAR(32) NOT NULL DEFAULT 'running',

    -- Trigger: manual, automatic, scheduled
    triggered_by VARCHAR(32) NOT NULL DEFAULT 'automatic',
    triggered_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Sources processed in this run
    sources_processed TEXT[],

    -- Execution results
    items_scraped INTEGER NOT NULL DEFAULT 0,
    items_failed INTEGER NOT NULL DEFAULT 0,
    items_duplicate INTEGER NOT NULL DEFAULT 0,

    -- Error information
    errors JSONB DEFAULT '[]'::jsonb,
    error_message TEXT,

    -- Configuration snapshot
    config_snapshot JSONB,

    -- Metadata
    notes TEXT,
    extra_metadata JSONB
);

-- Create indexes on scraping_runs
CREATE INDEX IF NOT EXISTS idx_scraping_runs_started_at ON scraping_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_scraping_runs_status ON scraping_runs(status);

-- Set all existing scraping_run_id values to NULL (since they reference non-existent runs)
UPDATE scraping_items
SET scraping_run_id = NULL
WHERE scraping_run_id IS NOT NULL;

-- Add FK constraint to scraping_items.scraping_run_id if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'scraping_items_scraping_run_id_fkey'
    ) THEN
        ALTER TABLE scraping_items
        ADD CONSTRAINT scraping_items_scraping_run_id_fkey
        FOREIGN KEY (scraping_run_id)
        REFERENCES scraping_runs(id)
        ON DELETE SET NULL;
    END IF;
END $$;

COMMIT;
