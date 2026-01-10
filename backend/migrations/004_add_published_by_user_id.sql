-- Migration to add published_by_user_id to publications table
-- This tracks which admin user published each publication (for auditing)

-- Add published_by_user_id column
ALTER TABLE publications
  ADD COLUMN published_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL;

-- Add index for performance
CREATE INDEX idx_publications_published_by_user ON publications(published_by_user_id);

-- Add comment explaining the column
COMMENT ON COLUMN publications.published_by_user_id IS
  'User who published this item. NULL for items published before this feature was added.';
