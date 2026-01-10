"""
API routes for scraping items (staging table).
Manages the full lifecycle of scraped content before publication.
"""
from datetime import datetime
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentAdmin
from app.api.schemas import (
    PaginatedScrapingItems,
    ScrapingItemCreate,
    ScrapingItemOut,
    ScrapingItemOutDetailed,
    ScrapingItemPublishRequest,
    ScrapingItemStats,
    ScrapingItemUpdate,
)
from app.core.slugify import slugify
from app.db.models import Publication, ScrapingItem, User
from app.db.session import get_db

router = APIRouter()


# ===== CREATE / UPSERT =====

@router.post("", response_model=ScrapingItemOut, status_code=201)
async def create_scraping_item(
    item: ScrapingItemCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create a new scraping item.
    Uses url_hash for deduplication - if url_hash already exists, returns existing item.
    """
    # Check if url_hash already exists
    existing_query = select(ScrapingItem).where(ScrapingItem.url_hash == item.url_hash)
    result = await db.execute(existing_query)
    existing = result.scalar_one_or_none()

    if existing:
        # Return existing item (deduplication)
        return existing

    # Create new item
    new_item = ScrapingItem(**item.model_dump())
    db.add(new_item)
    await db.commit()
    await db.refresh(new_item)

    return new_item


@router.post("/upsert", response_model=ScrapingItemOut)
async def upsert_scraping_item(
    item: ScrapingItemCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Upsert (insert or update) a scraping item based on url_hash.

    If an item with the same url_hash exists:
    - Updates content_hash, content, and other fields
    - Keeps the original scraped_at timestamp
    - Increments a counter if content changed

    If no item exists:
    - Creates a new item

    This is the recommended endpoint for scrapers to avoid duplicates.
    """
    item_dict = item.model_dump()

    # PostgreSQL UPSERT using INSERT ... ON CONFLICT
    stmt = insert(ScrapingItem).values(**item_dict)

    # On conflict (url_hash already exists), update these fields
    stmt = stmt.on_conflict_do_update(
        index_elements=["url_hash"],
        set_={
            "content": item_dict["content"],
            "content_hash": item_dict["content_hash"],
            "title": item_dict["title"],
            "subtitle": item_dict["subtitle"],
            "summary": item_dict["summary"],
            "raw_html": item_dict["raw_html"],
            "author": item_dict["author"],
            "article_date": item_dict["article_date"],
            "tags": item_dict["tags"],
            "image_urls": item_dict["image_urls"],
            "video_urls": item_dict["video_urls"],
            "updated_at": datetime.utcnow(),
            # Keep original scraped_at - don't update it
        },
    ).returning(ScrapingItem)

    result = await db.execute(stmt)
    upserted_item = result.scalar_one()
    await db.commit()
    await db.refresh(upserted_item)

    return upserted_item


# ===== READ / LIST =====

@router.get("", response_model=PaginatedScrapingItems)
async def list_scraping_items(
    status: str | None = Query(None, description="Filter by status"),
    source_media: str | None = Query(None, description="Filter by source media"),
    date_from: datetime | None = Query(None, description="Filter articles from this date"),
    date_to: datetime | None = Query(None, description="Filter articles until this date"),
    search_text: str | None = Query(None, description="Search in title or content"),
    scraper_name: str | None = Query(None, description="Filter by scraper name"),
    has_errors: bool | None = Query(None, description="Filter items with errors"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    List scraping items with filters and pagination.

    Filters:
    - status: scraped, pending_review, ready_for_ai, processing_ai, ai_completed, ready_to_publish, published, discarded, error, duplicate
    - source_media: lagaceta, clarin, infobae, etc
    - date_from/date_to: Filter by article_date
    - search_text: Full-text search in title or content
    - scraper_name: Filter by scraper
    - has_errors: Show only items with errors
    """
    # Build query with filters
    query = select(ScrapingItem)
    conditions = []

    if status:
        conditions.append(ScrapingItem.status == status)

    if source_media:
        conditions.append(ScrapingItem.source_media == source_media)

    if date_from:
        conditions.append(ScrapingItem.article_date >= date_from)

    if date_to:
        conditions.append(ScrapingItem.article_date <= date_to)

    if scraper_name:
        conditions.append(ScrapingItem.scraper_name == scraper_name)

    if has_errors is not None:
        if has_errors:
            conditions.append(ScrapingItem.last_error.isnot(None))
        else:
            conditions.append(ScrapingItem.last_error.is_(None))

    if search_text:
        search_pattern = f"%{search_text}%"
        conditions.append(
            or_(
                ScrapingItem.title.ilike(search_pattern),
                ScrapingItem.content.ilike(search_pattern),
            )
        )

    if conditions:
        query = query.where(and_(*conditions))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Apply pagination and ordering
    query = query.order_by(ScrapingItem.scraped_at.desc()).limit(limit).offset(offset)

    # Execute query
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedScrapingItems(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get("/{item_id}", response_model=ScrapingItemOutDetailed)
async def get_scraping_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get a single scraping item by ID with all details.
    """
    query = select(ScrapingItem).where(ScrapingItem.id == item_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Scraping item not found")

    return item


# ===== UPDATE =====

@router.patch("/{item_id}", response_model=ScrapingItemOut)
async def update_scraping_item(
    item_id: uuid.UUID,
    updates: ScrapingItemUpdate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update a scraping item.

    Allows updating:
    - Status and status message
    - AI-generated data (title, summary, tags, category)
    - Error information
    - Metadata
    """
    # Get existing item
    query = select(ScrapingItem).where(ScrapingItem.id == item_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Scraping item not found")

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)

    # If status is being updated to processing_ai, ai_completed, or error, set timestamps
    if "status" in update_data:
        new_status = update_data["status"]
        if new_status == "processing_ai":
            # Mark as processing
            pass
        elif new_status == "ai_completed":
            # Mark AI processing as completed
            if not item.ai_processed_at:
                update_data["ai_processed_at"] = datetime.utcnow()
        elif new_status == "error":
            # Increment retry count and update error timestamp
            update_data["retry_count"] = item.retry_count + 1
            update_data["last_error_at"] = datetime.utcnow()

    for key, value in update_data.items():
        setattr(item, key, value)

    await db.commit()
    await db.refresh(item)

    return item


# ===== PUBLISH =====

@router.post("/{item_id}/publish", response_model=dict)
async def publish_scraping_item(
    item_id: uuid.UUID,
    publish_req: ScrapingItemPublishRequest,
    current_user: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create a publication from a scraping item.

    **Requires:** Admin authentication

    This endpoint:
    1. Creates a new Publication record
    2. Links it to the scraping item
    3. Records which admin user published it
    4. Updates scraping item status to 'published'
    5. Returns the created publication ID

    The scraping item can be published from any status except 'published' or 'discarded'.
    """
    # Get scraping item
    query = select(ScrapingItem).where(ScrapingItem.id == item_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Scraping item not found")

    # Check status - can't publish if already published or discarded
    if item.status in ("published", "discarded"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot publish item with status '{item.status}'.",
        )

    # Check if already published
    if item.publication_id:
        raise HTTPException(
            status_code=400,
            detail=f"Item already published. Publication ID: {item.publication_id}",
        )

    # Determine content to use (override or AI-generated or original)
    title = publish_req.override_title or item.ai_title or item.title
    summary = publish_req.override_summary or item.ai_summary or item.summary
    body = publish_req.override_body or item.content

    if not title:
        raise HTTPException(status_code=400, detail="Cannot publish without a title")

    # Generate slug
    slug_base = slugify(title)

    # Check if slug exists, append UUID if needed
    slug_query = select(Publication).where(Publication.slug == slug_base)
    slug_result = await db.execute(slug_query)
    if slug_result.scalar_one_or_none():
        # Slug exists, append short UUID
        slug_base = f"{slug_base}-{str(item_id)[:8]}"

    # Create publication
    # Link to scraping_item via scraping_item_id (new system)
    # scraped_article_id is left as NULL (that's the legacy system)
    publication = Publication(
        scraped_article_id=None,  # Legacy system - not used
        scraping_item_id=item_id,  # New scraping system
        agent_id=publish_req.agent_id,
        published_by_user_id=current_user.id,  # Track who published this
        state="published",
        title=title,
        slug=slug_base,
        summary=summary or "",
        body=body,
        category=item.ai_category,
        tags=item.ai_tags or item.tags or [],
        published_at=datetime.utcnow(),
    )

    db.add(publication)
    await db.flush()  # Get publication ID

    # Update scraping item
    item.publication_id = publication.id
    item.published_at = datetime.utcnow()
    item.status = "published"

    await db.commit()

    return {
        "success": True,
        "publication_id": str(publication.id),
        "slug": slug_base,
        "message": "Publication created successfully",
    }


# ===== DELETE =====

@router.delete("/{item_id}", status_code=204)
async def delete_scraping_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a scraping item.
    Only allowed for items that are NOT published.
    """
    # Get item
    query = select(ScrapingItem).where(ScrapingItem.id == item_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Scraping item not found")

    # Don't allow deletion of published items
    if item.status == "published" or item.publication_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete published items. Unpublish first or mark as discarded.",
        )

    # Delete
    stmt = delete(ScrapingItem).where(ScrapingItem.id == item_id)
    await db.execute(stmt)
    await db.commit()


# ===== STATS =====

@router.get("/stats/summary", response_model=ScrapingItemStats)
async def get_scraping_stats(
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get statistics about scraping items.

    Returns:
    - Total items
    - Count by status
    - Count by source media
    - Average AI tokens used
    - Total AI cost
    - Items with errors
    - Items ready for AI processing
    - Items ready to publish
    """
    # Total items
    total_query = select(func.count()).select_from(ScrapingItem)
    total_result = await db.execute(total_query)
    total_items = total_result.scalar_one()

    # By status
    status_query = select(
        ScrapingItem.status,
        func.count(ScrapingItem.id).label("count"),
    ).group_by(ScrapingItem.status)
    status_result = await db.execute(status_query)
    by_status = {row.status: row.count for row in status_result}

    # By source media
    media_query = select(
        ScrapingItem.source_media,
        func.count(ScrapingItem.id).label("count"),
    ).group_by(ScrapingItem.source_media)
    media_result = await db.execute(media_query)
    by_source_media = {row.source_media: row.count for row in media_result}

    # AI stats
    ai_stats_query = select(
        func.avg(ScrapingItem.ai_tokens_used).label("avg_tokens"),
        func.sum(ScrapingItem.ai_cost_usd).label("total_cost"),
    ).where(ScrapingItem.ai_tokens_used.isnot(None))
    ai_stats_result = await db.execute(ai_stats_query)
    ai_stats = ai_stats_result.one()

    # Items with errors
    errors_query = select(func.count()).select_from(ScrapingItem).where(
        ScrapingItem.last_error.isnot(None)
    )
    errors_result = await db.execute(errors_query)
    items_with_errors = errors_result.scalar_one()

    # Items ready for AI
    ready_ai_query = select(func.count()).select_from(ScrapingItem).where(
        ScrapingItem.status == "ready_for_ai"
    )
    ready_ai_result = await db.execute(ready_ai_query)
    items_ready_for_ai = ready_ai_result.scalar_one()

    # Items ready to publish
    ready_publish_query = select(func.count()).select_from(ScrapingItem).where(
        ScrapingItem.status == "ready_to_publish"
    )
    ready_publish_result = await db.execute(ready_publish_query)
    items_pending_publish = ready_publish_result.scalar_one()

    return ScrapingItemStats(
        total_items=total_items,
        by_status=by_status,
        by_source_media=by_source_media,
        avg_ai_tokens=float(ai_stats.avg_tokens) if ai_stats.avg_tokens else None,
        total_ai_cost_usd=float(ai_stats.total_cost) if ai_stats.total_cost else None,
        items_with_errors=items_with_errors,
        items_ready_for_ai=items_ready_for_ai,
        items_pending_publish=items_pending_publish,
    )


# ===== BULK OPERATIONS =====

@router.post("/bulk/mark-duplicates", response_model=dict)
async def mark_duplicates(
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Find and mark duplicate items based on content_hash.
    Keeps the first scraped item, marks others as 'duplicate'.
    """
    # Find duplicates by content_hash
    duplicates_query = (
        select(
            ScrapingItem.content_hash,
            func.array_agg(ScrapingItem.id).label("ids"),
            func.min(ScrapingItem.scraped_at).label("first_scraped"),
        )
        .group_by(ScrapingItem.content_hash)
        .having(func.count(ScrapingItem.id) > 1)
    )

    result = await db.execute(duplicates_query)
    duplicates = result.all()

    marked_count = 0

    for dup in duplicates:
        content_hash = dup.content_hash
        ids = dup.ids

        # Get all items with this content_hash, ordered by scraped_at
        items_query = (
            select(ScrapingItem)
            .where(ScrapingItem.content_hash == content_hash)
            .order_by(ScrapingItem.scraped_at.asc())
        )
        items_result = await db.execute(items_query)
        items = items_result.scalars().all()

        # Keep first, mark rest as duplicates
        for i, item in enumerate(items):
            if i > 0 and item.status != "duplicate":
                item.status = "duplicate"
                item.status_message = f"Duplicate of item {items[0].id}"
                marked_count += 1

    await db.commit()

    return {
        "success": True,
        "duplicate_groups_found": len(duplicates),
        "items_marked_as_duplicate": marked_count,
    }
