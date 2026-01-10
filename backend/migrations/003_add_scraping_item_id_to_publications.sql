-- Migration to add scraping_item_id to publications and ai_runs tables
-- This connects the new scraping_items system to publications

-- Add scraping_item_id to publications table
ALTER TABLE publications
  ADD COLUMN scraping_item_id UUID REFERENCES scraping_items(id) ON DELETE SET NULL;

-- Add scraping_item_id to ai_runs table
ALTER TABLE ai_runs
  ADD COLUMN scraping_item_id UUID REFERENCES scraping_items(id) ON DELETE CASCADE;

-- Add comments explaining the columns
COMMENT ON COLUMN publications.scraping_item_id IS
  'Foreign key to scraping_items table. New scraping system that replaces scraped_articles.';

COMMENT ON COLUMN ai_runs.scraping_item_id IS
  'Foreign key to scraping_items table for AI processing in new scraping system.';

-- Note: We don't add a check constraint because:
-- 1. Legacy publications only have scraped_article_id (31 items)
-- 2. New publications will only have scraping_item_id
-- 3. The constraint would require at least one to be NOT NULL, which is handled at application level
