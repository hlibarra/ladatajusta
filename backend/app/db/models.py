from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    preferred_reading_level: Mapped[str] = mapped_column(String(32), default="lo_central")  # sin_vueltas|lo_central|en_profundidad
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(500))
    specialization: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())

    publications: Mapped[list["Publication"]] = relationship(back_populates="agent")


class ScrapedArticle(Base):
    __tablename__ = "scraped_articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    source_name: Mapped[str] = mapped_column(String(80))
    source_url: Mapped[str] = mapped_column(String(2048), unique=True, index=True)

    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())

    text_hash: Mapped[str] = mapped_column(String(64), index=True)

    
    publication: Mapped[Optional["Publication"]] = relationship(back_populates="scraped_article", uselist=False)


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scraped_article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scraped_articles.id", ondelete="CASCADE"), unique=True, nullable=True
    )
    scraping_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scraping_items.id", ondelete="SET NULL"), unique=True, nullable=True, index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    state: Mapped[str] = mapped_column(String(32), default="draft", index=True)  # draft|published|discarded

    title: Mapped[str] = mapped_column(String(512))
    slug: Mapped[str] = mapped_column(String(512), unique=True, index=True)  # URL-friendly version of title
    summary: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)

    # Reading levels - Niveles de lectura
    content_sin_vueltas: Mapped[str | None] = mapped_column(Text, nullable=True)  # Ultra corto
    content_lo_central: Mapped[str | None] = mapped_column(Text, nullable=True)  # Esencial
    content_en_profundidad: Mapped[str | None] = mapped_column(Text, nullable=True)  # Explicativo con contexto

    # Multimedia - Images and videos
    # Format: [{"type": "image|video", "url": "...", "caption": "...", "order": 0}, ...]
    media: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True, default=list)

    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)

    # Featured publications
    is_featured: Mapped[bool] = mapped_column(default=False, index=True)
    featured_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Media coverage intensity (1-5 scale)
    pulso_informativo: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Origin type: how the publication was created
    # Values: "detected_media" (from scraping), "editorial_ia" (AI editorial), etc.
    origin_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scraped_article: Mapped[Optional["ScrapedArticle"]] = relationship(back_populates="publication")
    scraping_item: Mapped[Optional["ScrapingItem"]] = relationship(foreign_keys=[scraping_item_id])
    agent: Mapped[Optional["Agent"]] = relationship(back_populates="publications")
    published_by_user: Mapped[Optional["User"]] = relationship(foreign_keys=[published_by_user_id])


class AIRun(Base):
    __tablename__ = "ai_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scraped_article_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scraped_articles.id"), nullable=True)
    scraping_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scraping_items.id", ondelete="CASCADE"), nullable=True, index=True)
    publication_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("publications.id"), nullable=True)

    agent: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32), default="ok")

    input_text: Mapped[str] = mapped_column(Text)
    output_text: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())


class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publication_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("publications.id", ondelete="CASCADE"), index=True)

    vote_type: Mapped[str] = mapped_column(String(16), index=True)  # hot|cold
    voter_key: Mapped[str] = mapped_column(String(128), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())

    __table_args__ = (
        UniqueConstraint("publication_id", "voter_key", name="uq_vote_pub_voter"),
        Index("ix_votes_pub_type", "publication_id", "vote_type"),
    )


class RSSFeed(Base):
    __tablename__ = "rss_feeds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(2048), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetch_interval_minutes: Mapped[int] = mapped_column(default=60)
    error_count: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())


class Section(Base):
    """Navigation sections that group multiple categories"""
    __tablename__ = "sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Icon name for UI
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())

    # Relationship to category mappings
    category_mappings: Mapped[list["CategorySectionMapping"]] = relationship(back_populates="section", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_sections_order', 'display_order', 'is_active'),
    )


class CategorySectionMapping(Base):
    """Maps publication categories to navigation sections (many-to-many)"""
    __tablename__ = "category_section_mapping"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sections.id", ondelete="CASCADE"), index=True
    )
    category_name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())

    # Relationship to section
    section: Mapped["Section"] = relationship(back_populates="category_mappings")

    __table_args__ = (
        UniqueConstraint("section_id", "category_name", name="uq_section_category"),
        Index('idx_category_section_mapping_section', 'section_id'),
        Index('idx_category_section_mapping_category', 'category_name'),
    )


class ScrapingSource(Base):
    """
    Configuration and management of scraping sources (media outlets).
    Each source represents a media outlet that can be scraped.
    """
    __tablename__ = "scraping_sources"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Source identification
    name: Mapped[str] = mapped_column(String(100), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    media_type: Mapped[str] = mapped_column(String(50), index=True)

    # Configuration
    is_active: Mapped[bool] = mapped_column(default=False, index=True)
    scraper_type: Mapped[str] = mapped_column(String(50), default="web")
    base_url: Mapped[str] = mapped_column(Text)

    # Scraping settings
    sections_to_scrape: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True, default=list)
    scraping_interval_minutes: Mapped[int | None] = mapped_column(Integer, default=60, nullable=True)
    max_articles_per_run: Mapped[int | None] = mapped_column(Integer, default=50, nullable=True)

    # Scraper script configuration
    scraper_script_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    scraper_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # AI processing configuration
    ai_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status tracking
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_scrape_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_scrape_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_scrape_items_count: Mapped[int] = mapped_column(Integer, default=0)

    # Statistics
    total_items_scraped: Mapped[int] = mapped_column(Integer, default=0)
    total_scrape_runs: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Error handling
    consecutive_errors: Mapped[int] = mapped_column(Integer, default=0)
    max_consecutive_errors: Mapped[int] = mapped_column(Integer, default=5)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Metadata
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ScrapingItem(Base):
    """
    Staging table for all scraped content.
    Stores raw scraped data with full traceability, deduplication, and pipeline state management.
    """
    __tablename__ = "scraping_items"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ===== ORIGIN METADATA =====
    source_media: Mapped[str] = mapped_column(Text)  # lagaceta, clarin, infobae, etc
    source_section: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_url: Mapped[str] = mapped_column(Text)
    source_url_normalized: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ===== RAW SCRAPED DATA =====
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtitle: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    raw_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    article_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True, default=list)
    image_urls: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True, default=list)
    video_urls: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True, default=list)

    # ===== DEDUPLICATION HASHES =====
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # ===== SCRAPING TRACEABILITY =====
    scraper_name: Mapped[str] = mapped_column(String(100))
    scraper_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    scraping_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow(), index=True)
    scraping_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scraper_ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    scraper_user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ===== PIPELINE STATE =====
    # scraped, pending_review, ready_for_ai, processing_ai, ai_completed, ready_to_publish, published, discarded, error, duplicate
    status: Mapped[str] = mapped_column(Text, default="scraped", index=True)
    status_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ===== AI PROCESSING DATA =====
    ai_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True, default=list)
    ai_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    ai_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_processing_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ===== ERROR HANDLING & RETRIES =====
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_trace: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ===== PUBLICATION LINK =====
    publication_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publications.id", ondelete="SET NULL"), nullable=True, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ===== AUDIT FIELDS =====
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ===== METADATA & EXTENSIBILITY =====
    extra_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index('idx_scraping_items_media_date', 'source_media', 'article_date'),
        Index('idx_scraping_items_status_updated', 'status', 'status_updated_at'),
    )


class SiteConfig(Base):
    """
    Dynamic site configuration stored in database.
    Allows changing display and feature settings without code changes.
    """
    __tablename__ = "site_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="general")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
