-- Migration to make scraped_article_id nullable in publications table
-- This allows publications to be created from scraping_items instead of scraped_articles

-- Make scraped_article_id nullable
ALTER TABLE publications
  ALTER COLUMN scraped_article_id DROP NOT NULL;

-- Add comment explaining the change
COMMENT ON COLUMN publications.scraped_article_id IS
  'Legacy field for backward compatibility with old scraping system. Nullable to support new scraping_items workflow.';
