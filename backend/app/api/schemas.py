from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ScrapeRequest(BaseModel):
    source_name: str = Field(..., min_length=1, max_length=80)
    url: str = Field(..., min_length=10, max_length=2048)


class ScrapedArticleOut(BaseModel):
    id: uuid.UUID
    source_name: str
    source_url: str
    title: str | None
    extracted_text: str
    scraped_at: datetime


class AgentOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str
    specialization: str | None
    avatar_url: str | None


class MediaItem(BaseModel):
    """Multimedia item (image or video)"""
    type: str = Field(..., pattern="^(image|video)$")  # image or video
    url: str  # URL to the image or video embed
    caption: str | None = None  # Optional caption
    order: int = 0  # Display order


class PublicationOut(BaseModel):
    id: uuid.UUID
    state: str
    title: str
    slug: str
    summary: str
    body: str
    category: str | None
    tags: list[str]
    created_at: datetime
    published_at: datetime | None
    agent: AgentOut | None = None
    # Reading levels
    content_sin_vueltas: str | None = None
    content_lo_central: str | None = None
    content_en_profundidad: str | None = None
    # Multimedia
    media: list[MediaItem] = []
    image_url: str | None = None  # First image URL from media array


class VoteRequest(BaseModel):
    vote_type: str = Field(..., pattern="^(hot|cold)$")


class VoteTotalsOut(BaseModel):
    publication_id: uuid.UUID
    hot: int
    cold: int


class PublicationUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    body: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    content_sin_vueltas: str | None = None
    content_lo_central: str | None = None
    content_en_profundidad: str | None = None
    media: list[MediaItem] | None = None


class StateChange(BaseModel):
    state: str = Field(..., pattern="^(draft|published|discarded)$")


class PaginatedPublications(BaseModel):
    items: list[PublicationOut]
    total: int
    limit: int
    offset: int
    has_more: bool


class ReadingLevelPreference(BaseModel):
    preferred_reading_level: str = Field(..., pattern="^(sin_vueltas|lo_central|en_profundidad)$")


class UserPreferences(BaseModel):
    preferred_reading_level: str


# ===== SCRAPING ITEMS SCHEMAS =====

class ScrapingItemCreate(BaseModel):
    """Schema for creating a new scraping item"""
    # Origin metadata
    source_media: str = Field(..., min_length=1, max_length=20)
    source_section: str | None = None
    source_url: str = Field(..., min_length=1)
    source_url_normalized: str = Field(..., min_length=1)
    canonical_url: str | None = None

    # Raw scraped data
    title: str | None = None
    subtitle: str | None = None
    summary: str | None = None
    content: str = Field(..., min_length=1)
    raw_html: str | None = None
    author: str | None = None
    article_date: datetime | None = None
    tags: list[str] = []
    image_urls: list[str] = []
    video_urls: list[str] = []

    # Deduplication hashes
    content_hash: str = Field(..., min_length=64, max_length=64)
    url_hash: str = Field(..., min_length=64, max_length=64)

    # Scraping traceability
    scraper_name: str = Field(..., min_length=1, max_length=100)
    scraper_version: str | None = None
    scraping_run_id: uuid.UUID | None = None
    scraping_duration_ms: int | None = None
    scraper_ip_address: str | None = None
    scraper_user_agent: str | None = None

    # Optional metadata
    extra_metadata: dict | None = None


class ScrapingItemUpdate(BaseModel):
    """Schema for updating a scraping item"""
    # Allow updating status
    status: str | None = Field(None, pattern="^(scraped|pending_review|ready_for_ai|processing_ai|ai_completed|ready_to_publish|published|discarded|error|duplicate)$")
    status_message: str | None = None

    # Allow updating AI data
    ai_title: str | None = None
    ai_summary: str | None = None
    ai_tags: list[str] | None = None
    ai_category: str | None = None
    ai_model: str | None = None
    ai_prompt_version: str | None = None
    ai_tokens_used: int | None = None
    ai_cost_usd: float | None = None
    ai_metadata: dict | None = None

    # Error tracking
    last_error: str | None = None
    error_trace: str | None = None

    # Metadata
    extra_metadata: dict | None = None
    updated_by: str | None = None


class ScrapingItemOut(BaseModel):
    """Schema for scraping item output"""
    model_config = {"from_attributes": True}

    id: uuid.UUID

    # Origin
    source_media: str
    source_section: str | None
    source_url: str
    canonical_url: str | None

    # Data
    title: str | None
    subtitle: str | None
    summary: str | None
    content: str
    author: str | None
    article_date: datetime | None
    tags: list[str]
    image_urls: list[str]
    video_urls: list[str]

    # Hashes
    content_hash: str
    url_hash: str

    # Scraping metadata
    scraper_name: str
    scraper_version: str | None
    scraping_run_id: uuid.UUID | None
    scraped_at: datetime

    # Status
    status: str
    status_updated_at: datetime
    status_message: str | None

    # AI data
    ai_title: str | None
    ai_summary: str | None
    ai_tags: list[str] | None
    ai_category: str | None
    ai_model: str | None
    ai_processed_at: datetime | None

    # Error tracking
    retry_count: int
    max_retries: int
    last_error: str | None
    last_error_at: datetime | None

    # Publication link
    publication_id: uuid.UUID | None
    published_at: datetime | None

    # Audit
    created_at: datetime
    updated_at: datetime


class ScrapingItemOutDetailed(ScrapingItemOut):
    """Detailed schema including raw HTML and full error traces"""
    raw_html: str | None
    error_trace: str | None
    ai_tokens_used: int | None
    ai_cost_usd: float | None
    ai_metadata: dict | None
    extra_metadata: dict | None
    scraper_ip_address: str | None
    scraper_user_agent: str | None
    scraping_duration_ms: int | None
    ai_processing_duration_ms: int | None


class ScrapingItemFilters(BaseModel):
    """Filters for querying scraping items"""
    status: str | None = Field(None, pattern="^(scraped|pending_review|ready_for_ai|processing_ai|ai_completed|ready_to_publish|published|discarded|error|duplicate)$")
    source_media: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    search_text: str | None = None  # Search in title/content
    scraper_name: str | None = None
    has_errors: bool | None = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


class PaginatedScrapingItems(BaseModel):
    """Paginated response for scraping items"""
    items: list[ScrapingItemOut]
    total: int
    limit: int
    offset: int
    has_more: bool


class ScrapingItemPublishRequest(BaseModel):
    """Request to publish a scraping item (creates publication)"""
    agent_id: uuid.UUID | None = None
    override_title: str | None = None
    override_summary: str | None = None
    override_body: str | None = None


class ScrapingItemStats(BaseModel):
    """Statistics for scraping items"""
    total_items: int
    by_status: dict[str, int]
    by_source_media: dict[str, int]
    avg_ai_tokens: float | None
    total_ai_cost_usd: float | None
    items_with_errors: int
    items_ready_for_ai: int
    items_pending_publish: int
