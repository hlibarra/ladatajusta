-- Migration: Create scraping_sources table
-- Manages scraping source configurations (media outlets to scrape)

CREATE TABLE scraping_sources (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source identification
    name VARCHAR(100) NOT NULL UNIQUE,                  -- Display name (e.g., "La Gaceta")
    slug VARCHAR(100) NOT NULL UNIQUE,                  -- URL-friendly identifier (lagaceta)
    media_type VARCHAR(50) NOT NULL,                    -- Media type for scraping_items (lagaceta, clarin, etc)

    -- Configuration
    is_active BOOLEAN NOT NULL DEFAULT false,           -- Enable/disable scraping
    scraper_type VARCHAR(50) NOT NULL DEFAULT 'web',    -- web, rss, api
    base_url TEXT NOT NULL,                             -- Base URL of the media

    -- Scraping settings
    sections_to_scrape TEXT[],                          -- Array of sections to scrape (e.g., ['politica', 'economia'])
    scraping_interval_minutes INTEGER DEFAULT 60,       -- How often to scrape
    max_articles_per_run INTEGER DEFAULT 50,            -- Limit articles per scraping run

    -- Scraper script configuration
    scraper_script_path TEXT,                           -- Path to scraper script (e.g., 'scraping/lagaceta/scraper.py')
    scraper_config JSONB,                               -- Additional scraper-specific config

    -- Status tracking
    last_scraped_at TIMESTAMPTZ,                        -- When last scraped
    last_scrape_status VARCHAR(32),                     -- success, error, running
    last_scrape_message TEXT,                           -- Status message or error
    last_scrape_items_count INTEGER DEFAULT 0,          -- Items scraped in last run

    -- Statistics
    total_items_scraped INTEGER DEFAULT 0,              -- Total items ever scraped
    total_scrape_runs INTEGER DEFAULT 0,                -- Total scraping runs
    success_rate DECIMAL(5, 2),                         -- Success rate percentage

    -- Error handling
    consecutive_errors INTEGER DEFAULT 0,               -- Track consecutive failures
    max_consecutive_errors INTEGER DEFAULT 5,           -- Auto-disable after N errors

    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100),

    -- Metadata
    notes TEXT,                                         -- Admin notes
    extra_metadata JSONB                                -- Flexible field for additional data
);

-- Indexes
CREATE INDEX idx_scraping_sources_active ON scraping_sources(is_active) WHERE is_active = true;
CREATE INDEX idx_scraping_sources_slug ON scraping_sources(slug);
CREATE INDEX idx_scraping_sources_media_type ON scraping_sources(media_type);
CREATE INDEX idx_scraping_sources_last_scraped ON scraping_sources(last_scraped_at DESC NULLS LAST);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_scraping_sources_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_scraping_sources_updated_at
    BEFORE UPDATE ON scraping_sources
    FOR EACH ROW
    EXECUTE FUNCTION update_scraping_sources_updated_at();

-- Insert La Gaceta as the default active source
INSERT INTO scraping_sources (
    name,
    slug,
    media_type,
    is_active,
    scraper_type,
    base_url,
    sections_to_scrape,
    scraping_interval_minutes,
    max_articles_per_run,
    scraper_script_path,
    scraper_config,
    notes
) VALUES (
    'La Gaceta',
    'lagaceta',
    'lagaceta',
    true,
    'web',
    'https://www.lagaceta.com.ar',
    ARRAY['politica', 'economia', 'sociedad', 'policiales', 'deportes'],
    60,
    50,
    'lagaceta/scrape_lagaceta_db.py',
    '{"use_playwright": true, "headless": false}'::jsonb,
    'Scraper principal para La Gaceta de Tucumán'
);

-- Insert other common media sources (disabled by default)
INSERT INTO scraping_sources (
    name, slug, media_type, is_active, scraper_type, base_url, scraping_interval_minutes, notes
) VALUES
    ('Clarín', 'clarin', 'clarin', false, 'web', 'https://www.clarin.com', 120, 'Medio nacional'),
    ('La Nación', 'lanacion', 'lanacion', false, 'web', 'https://www.lanacion.com.ar', 120, 'Medio nacional'),
    ('Infobae', 'infobae', 'infobae', false, 'web', 'https://www.infobae.com', 90, 'Medio digital'),
    ('Página/12', 'pagina12', 'pagina12', false, 'web', 'https://www.pagina12.com.ar', 120, 'Medio nacional'),
    ('Perfil', 'perfil', 'perfil', false, 'web', 'https://www.perfil.com', 120, 'Medio nacional');

-- Comments
COMMENT ON TABLE scraping_sources IS 'Configuration and management of scraping sources (media outlets)';
COMMENT ON COLUMN scraping_sources.is_active IS 'Enable or disable scraping for this source';
COMMENT ON COLUMN scraping_sources.scraper_config IS 'JSONB field for scraper-specific configuration like credentials, timeouts, etc';
COMMENT ON COLUMN scraping_sources.consecutive_errors IS 'Auto-incremented on errors, reset on success. Source auto-disabled if reaches max_consecutive_errors';
