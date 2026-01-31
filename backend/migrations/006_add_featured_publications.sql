-- Migration 006: Add featured publications support
-- Adds fields to mark publications as featured and order them

ALTER TABLE publications
  ADD COLUMN is_featured BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN featured_order INTEGER;

-- Index for querying featured publications
CREATE INDEX idx_publications_featured ON publications(is_featured, featured_order) WHERE is_featured = true;

-- Constraint: featured_order must be unique when not null
CREATE UNIQUE INDEX uq_publications_featured_order ON publications(featured_order) WHERE featured_order IS NOT NULL;

COMMENT ON COLUMN publications.is_featured IS 'Whether this publication is featured on the homepage';
COMMENT ON COLUMN publications.featured_order IS 'Display order for featured publications (1-4, lower = first)';
