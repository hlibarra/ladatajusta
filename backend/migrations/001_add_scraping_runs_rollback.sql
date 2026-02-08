-- Rollback migration: 001_add_scraping_runs
-- Created: 2026-02-06
-- Description: Rollback scraping_runs table and FK constraint

BEGIN;

-- Drop FK constraint from scraping_items if it exists
ALTER TABLE scraping_items
DROP CONSTRAINT IF EXISTS scraping_items_scraping_run_id_fkey;

-- Drop scraping_runs table
DROP TABLE IF EXISTS scraping_runs CASCADE;

COMMIT;
