-- Migration 010: Add origin_type field to publications
-- Tracks how the publication was created (scraping, editorial, etc.)

ALTER TABLE publications
  ADD COLUMN origin_type VARCHAR(50);

-- Index for filtering by origin type
CREATE INDEX idx_publications_origin_type ON publications(origin_type) WHERE origin_type IS NOT NULL;

-- Comment explaining the field
COMMENT ON COLUMN publications.origin_type IS 'Origin type of the publication: detected_media (from scraping), editorial_ia (AI editorial), etc.';

-- Update existing publications that came from scraping items
UPDATE publications
SET origin_type = 'detected_media'
WHERE scraping_item_id IS NOT NULL AND origin_type IS NULL;
