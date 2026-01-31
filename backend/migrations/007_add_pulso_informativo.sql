-- Migration 007: Add pulso_informativo field to publications
-- Adds a field to measure media coverage intensity (1-5 scale)

ALTER TABLE publications
  ADD COLUMN pulso_informativo INTEGER CHECK (pulso_informativo >= 1 AND pulso_informativo <= 5);

-- Index for querying by pulso_informativo
CREATE INDEX idx_publications_pulso ON publications(pulso_informativo) WHERE pulso_informativo IS NOT NULL;

COMMENT ON COLUMN publications.pulso_informativo IS 'Media coverage intensity: 1-5 scale (1=low, 5=high coverage in reference media)';
