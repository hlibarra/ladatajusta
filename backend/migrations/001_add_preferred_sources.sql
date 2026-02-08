-- Add preferred_sources column to users table
-- Migration: 001_add_preferred_sources
-- Date: 2026-02-06

ALTER TABLE users
ADD COLUMN IF NOT EXISTS preferred_sources JSONB DEFAULT NULL;

-- Add comment to document the column
COMMENT ON COLUMN users.preferred_sources IS 'Array of source IDs that the user prefers for scraping';
