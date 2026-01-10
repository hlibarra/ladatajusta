-- Useful SQL queries for scraping_items table
-- These queries can be used for monitoring, analysis, and debugging

-- ===== DASHBOARD QUERIES =====

-- Items by status (for dashboard)
SELECT
    status,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM scraping_items
GROUP BY status
ORDER BY count DESC;

-- Items by source media (last 7 days)
SELECT
    source_media,
    COUNT(*) as total,
    SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published,
    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
FROM scraping_items
WHERE scraped_at > NOW() - INTERVAL '7 days'
GROUP BY source_media
ORDER BY total DESC;

-- Recent activity (last 24 hours)
SELECT
    DATE_TRUNC('hour', scraped_at) as hour,
    COUNT(*) as items_scraped,
    COUNT(DISTINCT scraper_name) as scrapers_active
FROM scraping_items
WHERE scraped_at > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC;

-- ===== ERROR MONITORING =====

-- Items with errors (need attention)
SELECT
    id,
    source_media,
    title,
    last_error,
    retry_count,
    max_retries,
    last_error_at
FROM scraping_items
WHERE status = 'error'
  AND retry_count < max_retries
ORDER BY last_error_at DESC
LIMIT 50;

-- Error rate by scraper
SELECT
    scraper_name,
    COUNT(*) as total_items,
    SUM(CASE WHEN last_error IS NOT NULL THEN 1 ELSE 0 END) as items_with_errors,
    ROUND(SUM(CASE WHEN last_error IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as error_rate
FROM scraping_items
WHERE scraped_at > NOW() - INTERVAL '7 days'
GROUP BY scraper_name
ORDER BY error_rate DESC;

-- Most common errors
SELECT
    SUBSTRING(last_error, 1, 100) as error_prefix,
    COUNT(*) as occurrences
FROM scraping_items
WHERE last_error IS NOT NULL
  AND scraped_at > NOW() - INTERVAL '7 days'
GROUP BY error_prefix
ORDER BY occurrences DESC
LIMIT 20;

-- ===== DEDUPLICATION ANALYSIS =====

-- Find duplicates by content_hash
SELECT
    content_hash,
    COUNT(*) as duplicate_count,
    ARRAY_AGG(id ORDER BY scraped_at) as item_ids,
    ARRAY_AGG(source_url ORDER BY scraped_at) as urls,
    MIN(scraped_at) as first_seen,
    MAX(scraped_at) as last_seen
FROM scraping_items
GROUP BY content_hash
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC
LIMIT 100;

-- Items that share URLs (should be caught by url_hash unique constraint)
SELECT
    source_url_normalized,
    COUNT(*) as count,
    ARRAY_AGG(DISTINCT source_media) as sources
FROM scraping_items
GROUP BY source_url_normalized
HAVING COUNT(*) > 1
LIMIT 100;

-- Cross-media duplicates (same content from different sources)
SELECT
    si1.content_hash,
    si1.title,
    ARRAY_AGG(DISTINCT si1.source_media) as sources,
    COUNT(DISTINCT si1.id) as item_count
FROM scraping_items si1
GROUP BY si1.content_hash, si1.title
HAVING COUNT(DISTINCT si1.source_media) > 1
ORDER BY item_count DESC
LIMIT 50;

-- ===== AI PROCESSING STATS =====

-- AI usage summary
SELECT
    ai_model,
    COUNT(*) as items_processed,
    SUM(ai_tokens_used) as total_tokens,
    AVG(ai_tokens_used) as avg_tokens,
    SUM(ai_cost_usd) as total_cost_usd,
    AVG(ai_processing_duration_ms) as avg_duration_ms
FROM scraping_items
WHERE ai_model IS NOT NULL
GROUP BY ai_model
ORDER BY items_processed DESC;

-- AI processing over time (daily)
SELECT
    DATE_TRUNC('day', ai_processed_at) as day,
    COUNT(*) as items_processed,
    SUM(ai_tokens_used) as total_tokens,
    SUM(ai_cost_usd) as total_cost_usd
FROM scraping_items
WHERE ai_processed_at IS NOT NULL
  AND ai_processed_at > NOW() - INTERVAL '30 days'
GROUP BY day
ORDER BY day DESC;

-- Items ready for AI processing
SELECT
    id,
    source_media,
    title,
    scraped_at,
    CHAR_LENGTH(content) as content_length
FROM scraping_items
WHERE status = 'ready_for_ai'
  AND retry_count < max_retries
ORDER BY scraped_at ASC
LIMIT 100;

-- ===== PIPELINE MONITORING =====

-- Pipeline bottleneck analysis (time in each status)
SELECT
    status,
    COUNT(*) as items,
    AVG(EXTRACT(EPOCH FROM (COALESCE(status_updated_at, NOW()) - scraped_at))) / 3600 as avg_hours_in_status
FROM scraping_items
WHERE status != 'published'
GROUP BY status
ORDER BY items DESC;

-- Items stuck in processing
SELECT
    id,
    source_media,
    title,
    status,
    scraped_at,
    status_updated_at,
    EXTRACT(EPOCH FROM (NOW() - status_updated_at)) / 3600 as hours_in_status
FROM scraping_items
WHERE status IN ('processing_ai', 'pending_review')
  AND status_updated_at < NOW() - INTERVAL '24 hours'
ORDER BY hours_in_status DESC
LIMIT 50;

-- Items ready to publish
SELECT
    id,
    source_media,
    title,
    ai_title,
    ai_category,
    ai_tags,
    scraped_at
FROM scraping_items
WHERE status = 'ready_to_publish'
ORDER BY scraped_at ASC
LIMIT 50;

-- ===== PERFORMANCE ANALYSIS =====

-- Scraping speed by scraper
SELECT
    scraper_name,
    COUNT(*) as total_items,
    AVG(scraping_duration_ms) as avg_duration_ms,
    MIN(scraping_duration_ms) as min_duration_ms,
    MAX(scraping_duration_ms) as max_duration_ms
FROM scraping_items
WHERE scraping_duration_ms IS NOT NULL
  AND scraped_at > NOW() - INTERVAL '7 days'
GROUP BY scraper_name
ORDER BY avg_duration_ms DESC;

-- Items by content size
SELECT
    CASE
        WHEN CHAR_LENGTH(content) < 500 THEN 'Very Short (< 500)'
        WHEN CHAR_LENGTH(content) < 1000 THEN 'Short (500-1000)'
        WHEN CHAR_LENGTH(content) < 3000 THEN 'Medium (1000-3000)'
        WHEN CHAR_LENGTH(content) < 5000 THEN 'Long (3000-5000)'
        ELSE 'Very Long (> 5000)'
    END as content_size,
    COUNT(*) as count
FROM scraping_items
GROUP BY content_size
ORDER BY
    CASE content_size
        WHEN 'Very Short (< 500)' THEN 1
        WHEN 'Short (500-1000)' THEN 2
        WHEN 'Medium (1000-3000)' THEN 3
        WHEN 'Long (3000-5000)' THEN 4
        ELSE 5
    END;

-- ===== CONTENT ANALYSIS =====

-- Most common tags from scraping
SELECT
    tag,
    COUNT(*) as count
FROM scraping_items,
     UNNEST(tags) as tag
WHERE tags IS NOT NULL
  AND scraped_at > NOW() - INTERVAL '30 days'
GROUP BY tag
ORDER BY count DESC
LIMIT 50;

-- Most common AI-suggested categories
SELECT
    ai_category,
    COUNT(*) as count
FROM scraping_items
WHERE ai_category IS NOT NULL
  AND ai_processed_at > NOW() - INTERVAL '30 days'
GROUP BY ai_category
ORDER BY count DESC
LIMIT 20;

-- Articles by date (when article was published, not scraped)
SELECT
    DATE_TRUNC('day', article_date) as day,
    COUNT(*) as articles
FROM scraping_items
WHERE article_date IS NOT NULL
  AND article_date > NOW() - INTERVAL '30 days'
GROUP BY day
ORDER BY day DESC;

-- ===== SCRAPING RUN ANALYSIS =====

-- Stats by scraping run
SELECT
    scraping_run_id,
    COUNT(*) as items_in_run,
    MIN(scraped_at) as run_start,
    MAX(scraped_at) as run_end,
    EXTRACT(EPOCH FROM (MAX(scraped_at) - MIN(scraped_at))) / 60 as duration_minutes,
    SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published_count
FROM scraping_items
WHERE scraping_run_id IS NOT NULL
  AND scraped_at > NOW() - INTERVAL '7 days'
GROUP BY scraping_run_id
ORDER BY run_start DESC
LIMIT 50;

-- ===== PUBLICATION SUCCESS RATE =====

-- Success rate (scraped → published)
SELECT
    source_media,
    COUNT(*) as total_scraped,
    SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published,
    ROUND(SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as publish_rate,
    AVG(EXTRACT(EPOCH FROM (published_at - scraped_at))) / 3600 as avg_hours_to_publish
FROM scraping_items
WHERE scraped_at > NOW() - INTERVAL '30 days'
GROUP BY source_media
ORDER BY total_scraped DESC;

-- ===== DATA QUALITY CHECKS =====

-- Items missing important fields
SELECT
    'Missing title' as issue,
    COUNT(*) as count
FROM scraping_items
WHERE title IS NULL OR TRIM(title) = ''
UNION ALL
SELECT
    'Missing content',
    COUNT(*)
FROM scraping_items
WHERE content IS NULL OR TRIM(content) = ''
UNION ALL
SELECT
    'Missing article_date',
    COUNT(*)
FROM scraping_items
WHERE article_date IS NULL
UNION ALL
SELECT
    'No images',
    COUNT(*)
FROM scraping_items
WHERE image_urls IS NULL OR ARRAY_LENGTH(image_urls, 1) = 0;

-- Items with article_date in future (data quality issue)
SELECT
    id,
    source_media,
    title,
    article_date,
    scraped_at
FROM scraping_items
WHERE article_date > NOW()
ORDER BY article_date DESC
LIMIT 100;

-- Items with very short content (might be scraping errors)
SELECT
    id,
    source_media,
    source_url,
    title,
    CHAR_LENGTH(content) as content_length
FROM scraping_items
WHERE CHAR_LENGTH(content) < 100
  AND status NOT IN ('discarded', 'duplicate')
ORDER BY content_length ASC
LIMIT 100;

-- ===== CLEANUP QUERIES =====

-- Items that can be archived (published > 90 days ago)
SELECT
    COUNT(*) as items_to_archive,
    SUM(CHAR_LENGTH(raw_html)) / (1024 * 1024) as mb_html_to_archive,
    SUM(CHAR_LENGTH(content)) / (1024 * 1024) as mb_content_to_archive
FROM scraping_items
WHERE status = 'published'
  AND published_at < NOW() - INTERVAL '90 days';

-- Items that can be deleted (old errors and discarded)
SELECT
    status,
    COUNT(*) as items_to_delete
FROM scraping_items
WHERE (
    (status = 'error' AND retry_count >= max_retries AND last_error_at < NOW() - INTERVAL '30 days')
    OR
    (status = 'discarded' AND created_at < NOW() - INTERVAL '90 days')
)
GROUP BY status;

-- ===== USEFUL FUNCTIONS =====

-- Get pipeline statistics for a specific item
CREATE OR REPLACE FUNCTION get_item_timeline(item_uuid UUID)
RETURNS TABLE (
    event VARCHAR,
    timestamp TIMESTAMPTZ,
    duration_from_previous INTERVAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        'Scraped'::VARCHAR,
        scraped_at,
        NULL::INTERVAL
    FROM scraping_items WHERE id = item_uuid
    UNION ALL
    SELECT
        'AI Processed',
        ai_processed_at,
        ai_processed_at - scraped_at
    FROM scraping_items WHERE id = item_uuid AND ai_processed_at IS NOT NULL
    UNION ALL
    SELECT
        'Published',
        published_at,
        published_at - COALESCE(ai_processed_at, scraped_at)
    FROM scraping_items WHERE id = item_uuid AND published_at IS NOT NULL
    ORDER BY timestamp;
END;
$$ LANGUAGE plpgsql;

-- Example usage:
-- SELECT * FROM get_item_timeline('uuid-here');
