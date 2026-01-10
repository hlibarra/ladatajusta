# Scraping Items - Staging Table System

## Overview

The `scraping_items` table is a **staging table** that stores all scraped content before it becomes a publication. It provides:

- ✅ **Full traceability** of where content came from
- ✅ **Deduplication** using content and URL hashes
- ✅ **Pipeline state management** (scraped → AI processing → ready to publish → published)
- ✅ **Error tracking and retry logic**
- ✅ **AI processing metadata** (model, tokens, cost)
- ✅ **Audit trail** (who, when, what changed)

## Architecture

```
┌─────────────┐
│   Scraper   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│   scraping_items (staging)      │
│   - Raw scraped data            │
│   - Hashes for dedup            │
│   - Pipeline status             │
│   - Error tracking              │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   AI Pipeline                   │
│   - Normalize content           │
│   - Generate summaries          │
│   - Extract tags/category       │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   publications (final)          │
│   - Published content           │
│   - Reading levels              │
│   - Links to scraping_item      │
└─────────────────────────────────┘
```

## Database Schema

### Table: `scraping_items`

| Field | Type | Description |
|-------|------|-------------|
| **Origin Metadata** | | |
| `source_media` | VARCHAR(20) | Media outlet (lagaceta, clarin, infobae, etc) |
| `source_section` | VARCHAR(100) | Section (politica, economia, deportes, etc) |
| `source_url` | TEXT | Original URL |
| `source_url_normalized` | TEXT | Normalized URL for dedup |
| `canonical_url` | TEXT | Canonical URL if exists |
| **Raw Data** | | |
| `title` | TEXT | Article title |
| `subtitle` | TEXT | Subtitle/lead |
| `summary` | TEXT | Brief summary |
| `content` | TEXT | Full article content |
| `raw_html` | TEXT | Original HTML for audit |
| `author` | VARCHAR(255) | Article author |
| `article_date` | TIMESTAMPTZ | Publication date from source |
| `tags` | TEXT[] | Original tags from source |
| `image_urls` | TEXT[] | Image URLs found |
| `video_urls` | TEXT[] | Video URLs found |
| **Deduplication** | | |
| `content_hash` | VARCHAR(64) | SHA-256 hash of normalized content |
| `url_hash` | VARCHAR(64) | SHA-256 hash of normalized URL (UNIQUE) |
| **Scraping Metadata** | | |
| `scraper_name` | VARCHAR(100) | Scraper identifier |
| `scraper_version` | VARCHAR(20) | Scraper version |
| `scraping_run_id` | UUID | Batch/run identifier |
| `scraped_at` | TIMESTAMPTZ | When scraped |
| `scraping_duration_ms` | INTEGER | Scraping time (ms) |
| `scraper_ip_address` | INET | IP used for scraping |
| `scraper_user_agent` | TEXT | User-Agent used |
| **Pipeline State** | | |
| `status` | VARCHAR(32) | Current pipeline status (see below) |
| `status_updated_at` | TIMESTAMPTZ | When status last changed |
| `status_message` | TEXT | Additional status info |
| **AI Processing** | | |
| `ai_title` | TEXT | AI-generated title |
| `ai_summary` | TEXT | AI-generated summary |
| `ai_tags` | TEXT[] | AI-suggested tags |
| `ai_category` | VARCHAR(80) | AI-suggested category |
| `ai_model` | VARCHAR(50) | Model used (gpt-4o-mini, etc) |
| `ai_prompt_version` | VARCHAR(20) | Prompt version |
| `ai_tokens_used` | INTEGER | Total tokens consumed |
| `ai_cost_usd` | DECIMAL(10,6) | Estimated cost in USD |
| `ai_processed_at` | TIMESTAMPTZ | When AI processing completed |
| `ai_processing_duration_ms` | INTEGER | AI processing time |
| `ai_metadata` | JSONB | Additional AI data |
| **Error Handling** | | |
| `retry_count` | INTEGER | Number of retry attempts |
| `max_retries` | INTEGER | Maximum retries allowed |
| `last_error` | TEXT | Last error message |
| `last_error_at` | TIMESTAMPTZ | When last error occurred |
| `error_trace` | TEXT | Full error traceback |
| **Publication Link** | | |
| `publication_id` | UUID | Link to publications table |
| `published_at` | TIMESTAMPTZ | When publication was created |
| **Audit** | | |
| `created_at` | TIMESTAMPTZ | When created |
| `updated_at` | TIMESTAMPTZ | When last updated |
| `created_by` | VARCHAR(100) | User/system that created |
| `updated_by` | VARCHAR(100) | User/system that last updated |
| **Extensibility** | | |
| `extra_metadata` | JSONB | Flexible field for additional data |

### Pipeline Statuses

| Status | Description |
|--------|-------------|
| `scraped` | Just scraped, raw data |
| `pending_review` | Waiting for human/automated review |
| `ready_for_ai` | Approved for AI processing |
| `processing_ai` | Currently being processed by AI |
| `ai_completed` | AI processing done |
| `ready_to_publish` | Ready to create publication |
| `published` | Publication created and linked |
| `discarded` | Rejected/not relevant |
| `error` | Processing error |
| `duplicate` | Marked as duplicate |

## API Endpoints

Base path: `/api/scraping-items`

### Create/Upsert

#### `POST /scraping-items`
Create a new scraping item. Returns existing item if `url_hash` already exists (deduplication).

#### `POST /scraping-items/upsert` ⭐ **RECOMMENDED**
Upsert (insert or update) based on `url_hash`. Updates content if URL already exists.

**Request Body:**
```json
{
  "source_media": "lagaceta",
  "source_section": "politica",
  "source_url": "https://www.lagaceta.com.ar/nota/123456",
  "source_url_normalized": "https://lagaceta.com.ar/nota/123456",
  "title": "Example Article",
  "content": "Full article content...",
  "content_hash": "abc123...",
  "url_hash": "def456...",
  "scraper_name": "rss_scraper",
  "scraper_version": "1.0.0"
}
```

### Read/Query

#### `GET /scraping-items`
List scraping items with filters and pagination.

**Query Parameters:**
- `status`: Filter by status
- `source_media`: Filter by media outlet
- `date_from`, `date_to`: Filter by article date
- `search_text`: Full-text search in title/content
- `scraper_name`: Filter by scraper
- `has_errors`: Show only items with errors
- `limit`, `offset`: Pagination

**Example:**
```bash
GET /api/scraping-items?status=ready_for_ai&source_media=lagaceta&limit=20
```

#### `GET /scraping-items/{id}`
Get a single scraping item with all details.

### Update

#### `PATCH /scraping-items/{id}`
Update a scraping item.

**Request Body:**
```json
{
  "status": "ai_completed",
  "ai_title": "AI-generated title",
  "ai_summary": "AI-generated summary",
  "ai_tags": ["politics", "argentina"],
  "ai_category": "politica",
  "ai_model": "gpt-4o-mini",
  "ai_tokens_used": 1250
}
```

### Publish

#### `POST /scraping-items/{id}/publish`
Create a publication from a scraping item.

**Request Body:**
```json
{
  "agent_id": "uuid-of-agent",
  "override_title": "Optional custom title",
  "override_summary": "Optional custom summary"
}
```

**Response:**
```json
{
  "success": true,
  "publication_id": "uuid-of-publication",
  "slug": "article-slug",
  "message": "Publication created successfully"
}
```

### Delete

#### `DELETE /scraping-items/{id}`
Delete a scraping item (only if not published).

### Stats

#### `GET /scraping-items/stats/summary`
Get statistics about scraping items.

**Response:**
```json
{
  "total_items": 1523,
  "by_status": {
    "scraped": 450,
    "ready_for_ai": 120,
    "ai_completed": 80,
    "published": 873
  },
  "by_source_media": {
    "lagaceta": 623,
    "clarin": 450,
    "infobae": 450
  },
  "avg_ai_tokens": 1245.5,
  "total_ai_cost_usd": 15.67,
  "items_with_errors": 23,
  "items_ready_for_ai": 120,
  "items_pending_publish": 80
}
```

### Bulk Operations

#### `POST /scraping-items/bulk/mark-duplicates`
Find and mark duplicate items based on `content_hash`.

## Usage Examples

### Example 1: Scraper Integration

```python
from app.scrape.deduplication import (
    generate_content_hash,
    generate_url_hash,
    normalize_url,
)
import httpx

async def scrape_and_save(url: str):
    # Scrape content
    scraped_data = await scrape_article(url)

    # Generate hashes
    normalized_url = normalize_url(url)
    url_hash = generate_url_hash(url)
    content_hash = generate_content_hash(scraped_data['content'])

    # Prepare payload
    payload = {
        "source_media": "lagaceta",
        "source_url": url,
        "source_url_normalized": normalized_url,
        "url_hash": url_hash,
        "content_hash": content_hash,
        "title": scraped_data['title'],
        "content": scraped_data['content'],
        "scraper_name": "my_scraper",
        # ... other fields
    }

    # Send to API (upsert for deduplication)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/scraping-items/upsert",
            json=payload
        )
        return response.json()
```

### Example 2: AI Pipeline Integration

```python
async def process_with_ai(item_id: str):
    # Get item
    item = await get_scraping_item(item_id)

    # Update status to processing
    await update_item(item_id, {"status": "processing_ai"})

    try:
        # Run AI processing
        ai_result = await ai_pipeline.process(item['content'])

        # Update with AI results
        await update_item(item_id, {
            "status": "ai_completed",
            "ai_title": ai_result['title'],
            "ai_summary": ai_result['summary'],
            "ai_tags": ai_result['tags'],
            "ai_model": "gpt-4o-mini",
            "ai_tokens_used": ai_result['tokens']
        })
    except Exception as e:
        # Mark as error
        await update_item(item_id, {
            "status": "error",
            "last_error": str(e)
        })
```

### Example 3: Publishing

```python
async def publish_item(item_id: str, agent_id: str):
    response = await client.post(
        f"http://localhost:8000/api/scraping-items/{item_id}/publish",
        json={"agent_id": agent_id}
    )
    return response.json()
```

## Deduplication Strategy

### URL Deduplication

1. **Normalize URL**: Remove tracking parameters, normalize case, remove trailing slashes
2. **Generate hash**: SHA-256 of normalized URL
3. **Check on insert**: `url_hash` has UNIQUE constraint
4. **Upsert behavior**: If URL exists, update content (handles article updates)

### Content Deduplication

1. **Normalize content**: Lowercase, remove extra whitespace
2. **Generate hash**: SHA-256 of normalized content
3. **Detect duplicates**: Find items with same `content_hash`
4. **Bulk operation**: `/bulk/mark-duplicates` endpoint finds and marks duplicates

## Migration

To create the table in your database:

```bash
# Using psql
psql -U ladatajusta -d ladatajusta -f backend/migrations/001_create_scraping_items.sql

# Or run the SQL directly in your database client
```

## Best Practices

1. **Always use upsert endpoint** for scrapers to avoid duplicates
2. **Set scraping_run_id** for batch operations to track scraping sessions
3. **Normalize URLs** before hashing to ensure consistent deduplication
4. **Store raw_html** for audit and re-processing capabilities
5. **Use status transitions** properly: scraped → ready_for_ai → processing_ai → ai_completed → ready_to_publish → published
6. **Monitor errors**: Query items with `has_errors=true` and retry failed items
7. **Archive old items**: Periodically archive published items to keep table performant

## Performance Considerations

- Indexes are optimized for common queries (status, media, date)
- Use pagination for large result sets
- Consider partitioning by `scraped_at` for very large datasets (millions of items)
- Use materialized views for complex stats queries

## Monitoring

Key metrics to track:

- Items by status (dashboard)
- Error rate (items with `last_error`)
- AI processing cost (`total_ai_cost_usd`)
- Duplicate rate (content_hash collisions)
- Scraping throughput (items per hour/day)
- Time in each status (pipeline bottlenecks)

## Future Enhancements

- [ ] Add similarity detection beyond exact hash matching
- [ ] Implement automatic retry scheduling for error status
- [ ] Add content quality scoring
- [ ] Implement archiving strategy for old items
- [ ] Add webhook notifications for status changes
- [ ] Implement rate limiting per source_media
