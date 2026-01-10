-- Migration: Create scraping_items table for staging scraped content
-- This table stores ALL scraped data with full traceability, deduplication, and pipeline state management

-- Create ENUM types for better type safety and performance
CREATE TYPE scraping_status AS ENUM (
    'scraped',              -- Just scraped, raw data
    'pending_review',       -- Waiting for human/automated review
    'ready_for_ai',         -- Approved for AI processing
    'processing_ai',        -- Currently being processed by AI
    'ai_completed',         -- AI processing done
    'ready_to_publish',     -- Ready to create publication
    'published',            -- Publication created and linked
    'discarded',            -- Rejected/not relevant
    'error',                -- Processing error
    'duplicate'             -- Marked as duplicate
);

CREATE TYPE source_media AS ENUM (
    'lagaceta',
    'clarin',
    'infobae',
    'lanacion',
    'pagina12',
    'perfil',
    'ambito',
    'cronista',
    'other'
);

-- Main scraping staging table
CREATE TABLE scraping_items (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- ===== ORIGIN METADATA =====
    source_media source_media NOT NULL,                    -- Media outlet
    source_section VARCHAR(100),                           -- Section (politica, economia, etc)
    source_url TEXT NOT NULL,                              -- Original URL
    source_url_normalized TEXT NOT NULL,                   -- Normalized URL for dedup
    canonical_url TEXT,                                    -- Canonical URL if exists

    -- ===== RAW SCRAPED DATA =====
    title TEXT,                                            -- Article title
    subtitle TEXT,                                         -- Subtitle/lead if exists
    summary TEXT,                                          -- Short summary/description
    content TEXT NOT NULL,                                 -- Full article content
    raw_html TEXT,                                         -- Original HTML for audit
    author VARCHAR(255),                                   -- Article author
    article_date TIMESTAMPTZ,                              -- Publication date from source
    tags TEXT[],                                           -- Original tags from source
    image_urls TEXT[],                                     -- Image URLs found
    video_urls TEXT[],                                     -- Video URLs found

    -- ===== DEDUPLICATION HASHES =====
    content_hash VARCHAR(64) NOT NULL,                     -- SHA-256 of normalized content
    url_hash VARCHAR(64) NOT NULL,                         -- SHA-256 of normalized URL

    -- ===== SCRAPING TRACEABILITY =====
    scraper_name VARCHAR(100) NOT NULL,                    -- Scraper identifier (rss_scraper, web_scraper, etc)
    scraper_version VARCHAR(20),                           -- Scraper version
    scraping_run_id UUID,                                  -- Batch/run identifier for this scraping session
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),         -- When scraped
    scraping_duration_ms INTEGER,                          -- How long scraping took (ms)
    scraper_ip_address INET,                               -- IP used for scraping
    scraper_user_agent TEXT,                               -- User-Agent used

    -- ===== PIPELINE STATE =====
    status scraping_status NOT NULL DEFAULT 'scraped',     -- Current pipeline status
    status_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),  -- When status last changed
    status_message TEXT,                                   -- Additional status info/reason

    -- ===== AI PROCESSING DATA =====
    ai_title TEXT,                                         -- AI-generated title
    ai_summary TEXT,                                       -- AI-generated summary
    ai_tags TEXT[],                                        -- AI-suggested tags
    ai_category VARCHAR(80),                               -- AI-suggested category
    ai_model VARCHAR(50),                                  -- Model used (gpt-4o-mini, etc)
    ai_prompt_version VARCHAR(20),                         -- Prompt version for tracking
    ai_tokens_used INTEGER,                                -- Total tokens consumed
    ai_cost_usd DECIMAL(10, 6),                            -- Estimated cost in USD
    ai_processed_at TIMESTAMPTZ,                           -- When AI processing completed
    ai_processing_duration_ms INTEGER,                     -- AI processing time
    ai_metadata JSONB,                                     -- Additional AI data (confidence, etc)

    -- ===== ERROR HANDLING & RETRIES =====
    retry_count INTEGER NOT NULL DEFAULT 0,                -- Number of retry attempts
    max_retries INTEGER NOT NULL DEFAULT 3,                -- Maximum retries allowed
    last_error TEXT,                                       -- Last error message
    last_error_at TIMESTAMPTZ,                             -- When last error occurred
    error_trace TEXT,                                      -- Full error traceback for debugging

    -- ===== PUBLICATION LINK =====
    publication_id UUID,                                   -- Link to publications table (nullable)
    published_at TIMESTAMPTZ,                              -- When publication was created

    -- ===== AUDIT FIELDS =====
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),                               -- User/system that created
    updated_by VARCHAR(100),                               -- User/system that last updated

    -- ===== METADATA & EXTENSIBILITY =====
    extra_metadata JSONB,                                  -- Flexible field for additional data

    -- Foreign key to publications (if table exists)
    CONSTRAINT fk_scraping_publication FOREIGN KEY (publication_id)
        REFERENCES publications(id) ON DELETE SET NULL
);

-- ===== INDEXES FOR PERFORMANCE =====

-- Status queries (most common)
CREATE INDEX idx_scraping_items_status ON scraping_items(status) WHERE status != 'published' AND status != 'discarded';
CREATE INDEX idx_scraping_items_status_updated ON scraping_items(status, status_updated_at DESC);

-- Deduplication (critical)
CREATE UNIQUE INDEX idx_scraping_items_url_hash ON scraping_items(url_hash);
CREATE INDEX idx_scraping_items_content_hash ON scraping_items(content_hash);
CREATE INDEX idx_scraping_items_url_normalized ON scraping_items(source_url_normalized);

-- Source and date filtering
CREATE INDEX idx_scraping_items_media_date ON scraping_items(source_media, article_date DESC NULLS LAST);
CREATE INDEX idx_scraping_items_scraped_at ON scraping_items(scraped_at DESC);

-- Text search (for titulo/contenido)
CREATE INDEX idx_scraping_items_title_trgm ON scraping_items USING gin(title gin_trgm_ops);
CREATE INDEX idx_scraping_items_content_trgm ON scraping_items USING gin(content gin_trgm_ops);

-- Scraping run tracking
CREATE INDEX idx_scraping_items_run_id ON scraping_items(scraping_run_id) WHERE scraping_run_id IS NOT NULL;

-- Publication link
CREATE INDEX idx_scraping_items_publication ON scraping_items(publication_id) WHERE publication_id IS NOT NULL;

-- Error tracking and retries
CREATE INDEX idx_scraping_items_errors ON scraping_items(status, retry_count) WHERE status = 'error';

-- ===== CONSTRAINTS =====

-- Ensure content and URL hashes are always set
ALTER TABLE scraping_items ADD CONSTRAINT chk_content_hash_not_empty CHECK (length(content_hash) > 0);
ALTER TABLE scraping_items ADD CONSTRAINT chk_url_hash_not_empty CHECK (length(url_hash) > 0);

-- Ensure retry count doesn't exceed max retries
ALTER TABLE scraping_items ADD CONSTRAINT chk_retry_count_valid CHECK (retry_count <= max_retries);

-- Ensure published items have publication_id
ALTER TABLE scraping_items ADD CONSTRAINT chk_published_has_publication
    CHECK (status != 'published' OR publication_id IS NOT NULL);

-- Ensure article_date is not in the future
ALTER TABLE scraping_items ADD CONSTRAINT chk_article_date_not_future
    CHECK (article_date IS NULL OR article_date <= NOW());

-- ===== TRIGGER FOR UPDATED_AT =====
CREATE OR REPLACE FUNCTION update_scraping_items_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();

    -- Auto-update status_updated_at if status changed
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        NEW.status_updated_at = NOW();
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_scraping_items_updated_at
    BEFORE UPDATE ON scraping_items
    FOR EACH ROW
    EXECUTE FUNCTION update_scraping_items_updated_at();

-- ===== USEFUL VIEWS =====

-- View for items pending AI processing
CREATE VIEW scraping_items_pending_ai AS
SELECT
    id, source_media, title, source_url, article_date, scraped_at, retry_count
FROM scraping_items
WHERE status IN ('ready_for_ai', 'error')
  AND retry_count < max_retries
ORDER BY article_date DESC NULLS LAST, scraped_at DESC;

-- View for duplicate detection
CREATE VIEW scraping_duplicates AS
SELECT
    content_hash,
    COUNT(*) as duplicate_count,
    array_agg(id ORDER BY scraped_at DESC) as item_ids,
    array_agg(source_url ORDER BY scraped_at DESC) as urls,
    MIN(scraped_at) as first_scraped,
    MAX(scraped_at) as last_scraped
FROM scraping_items
GROUP BY content_hash
HAVING COUNT(*) > 1;

-- View for scraping stats by source
CREATE VIEW scraping_stats_by_source AS
SELECT
    source_media,
    status,
    COUNT(*) as count,
    MIN(scraped_at) as first_scrape,
    MAX(scraped_at) as last_scrape
FROM scraping_items
GROUP BY source_media, status
ORDER BY source_media, status;

-- ===== COMMENTS =====
COMMENT ON TABLE scraping_items IS 'Staging table for all scraped content with full traceability and pipeline management';
COMMENT ON COLUMN scraping_items.content_hash IS 'SHA-256 hash of normalized content for deduplication';
COMMENT ON COLUMN scraping_items.url_hash IS 'SHA-256 hash of normalized URL for deduplication';
COMMENT ON COLUMN scraping_items.status IS 'Pipeline state: scraped -> ready_for_ai -> ai_completed -> ready_to_publish -> published';
COMMENT ON COLUMN scraping_items.ai_metadata IS 'Flexible JSON field for AI-specific data like confidence scores, entity extraction, etc';
COMMENT ON COLUMN scraping_items.extra_metadata IS 'Flexible JSON field for source-specific or custom metadata';
