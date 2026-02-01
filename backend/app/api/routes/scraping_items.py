"""
API routes for scraping items (staging table).
Manages the full lifecycle of scraped content before publication.
"""
from datetime import datetime
from decimal import Decimal
from typing import Any
import uuid
import os
import json
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    AsyncOpenAI = None
    OPENAI_AVAILABLE = False

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

# OpenAI configuration for image generation
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DALLE_MODEL = "dall-e-3"
DALLE_SIZE = "1024x1024"
DALLE_QUALITY = "standard"

# Initialize OpenAI client
openai_client = None
if OPENAI_AVAILABLE and OPENAI_API_KEY:
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ===== ANTI-CLICKBAIT IMAGE SYSTEM =====
# Visual states for editorial images that reflect the information state, not the story

VISUAL_STATES = {
    "incertidumbre": {
        "name": "Incertidumbre",
        "description": "Algo que todavía no está definido",
        "prompt_elements": "incomplete geometric forms, floating elements, open spaces, gaps between shapes, unfinished lines, desaturated cool tones (slate gray, muted blue, soft white), elements that don't quite connect"
    },
    "tension": {
        "name": "Tensión",
        "description": "Fuerzas en oposición, negociación, conflicto moderado",
        "prompt_elements": "two opposing masses or blocks almost touching, converging diagonal lines, visual contrast between elements, balanced opposition, warm and cool tones in tension (deep blue vs burnt orange), compressed negative space"
    },
    "impacto": {
        "name": "Impacto",
        "description": "Decisión importante, fallo, anuncio fuerte",
        "prompt_elements": "solid defined central form, strong geometric presence, clear focal point, bold shapes, more saturated accent color (deep red or strong blue), radiating lines or emphasis marks, decisive composition"
    },
    "estabilidad": {
        "name": "Estabilidad",
        "description": "Normalidad, continuidad, dato sin sobresaltos",
        "prompt_elements": "horizontal composition, parallel lines, symmetrical balance, calm neutral tones (warm gray, soft beige, muted earth tones), grounded shapes, even spacing, harmonious proportions"
    },
    "cierre": {
        "name": "Cierre",
        "description": "Tema que se resuelve o se enfría",
        "prompt_elements": "closed forms, complete circles or contained shapes, elements converging to a point, resolved composition, cooling tones (soft gray transitioning to white), sense of completion, fading elements"
    }
}

# Base prompt for La Data Justa anti-clickbait images
ANTICLICKBAIT_BASE_PROMPT = """Create an abstract, minimalist editorial image for a news publication.

STYLE REQUIREMENTS:
- Ultra-minimalist and abstract composition
- NO text, NO people, NO faces, NO recognizable scenes
- Clean geometric forms: lines, blocks, circles, negative space
- Professional, sober color palette
- Editorial and trustworthy aesthetic
- Simple shapes that don't compete with headlines
- Modern graphic design approach, NOT illustration or artistic

COLOR PALETTE: Professional neutrals with one accent. Use slate grays, soft whites, muted earth tones. Accent colors should be desaturated and sophisticated.

COMPOSITION: Clean, balanced, with intentional use of negative space. The image should feel like a visual mood indicator, not a story illustration.

This is for "La Data Justa", a data-driven news outlet that values honesty over sensationalism."""

# Image storage configuration
# Check if running in Docker (volume mounted at /frontend_images)
# or locally (relative path to frontend)
if Path("/frontend_images").exists():
    # Running in Docker
    IMAGE_DIR = Path("/frontend_images/generated")
else:
    # Running locally
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    IMAGE_DIR = PROJECT_ROOT / "frontend" / "public" / "images" / "generated"

IMAGE_URL_PREFIX = "/images/generated"

# Ensure image directory exists
IMAGE_DIR.mkdir(parents=True, exist_ok=True)


async def download_and_save_image(url: str, filename: str) -> str:
    """
    Download image from DALL-E temporary URL and save to permanent storage.
    Returns the permanent URL path.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                filepath = IMAGE_DIR / filename
                filepath.write_bytes(response.content)
                return f"{IMAGE_URL_PREFIX}/{filename}"
            else:
                raise Exception(f"Failed to download image: HTTP {response.status_code}")
    except Exception as e:
        raise Exception(f"Error downloading image: {str(e)}")


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
    date_field: str | None = Query(None, description="Field to filter by date: scraped_at or status_updated_at"),
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
    - date_from/date_to: Filter by date (use date_field to select which field)
    - date_field: Which date field to filter (scraped_at or status_updated_at)
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

    # Determine which date field to filter by
    date_column = ScrapingItem.status_updated_at if date_field == "status_updated_at" else ScrapingItem.scraped_at

    if date_from:
        conditions.append(date_column >= date_from)

    if date_to:
        conditions.append(date_column <= date_to)

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

    # Extract reading levels from ai_metadata
    content_sin_vueltas = None
    content_lo_central = None
    content_en_profundidad = None

    if item.ai_metadata:
        content_sin_vueltas = item.ai_metadata.get("sin_vueltas")
        content_lo_central = item.ai_metadata.get("lo_central")
        content_en_profundidad = item.ai_metadata.get("en_profundidad")

    # Convert image_urls to media format
    media = []
    if item.image_urls:
        for idx, image_url in enumerate(item.image_urls):
            media.append({
                "type": "image",
                "url": image_url,
                "caption": "",  # Could be enhanced to extract caption from ai_metadata
                "order": idx
            })

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
        content_sin_vueltas=content_sin_vueltas,
        content_lo_central=content_lo_central,
        content_en_profundidad=content_en_profundidad,
        media=media if media else [],
        published_at=datetime.utcnow(),
        origin_type="detected_media",  # From scraping system
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


# ===== AI PROCESSING =====

# OpenAI text processing configuration
OPENAI_TEXT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
AI_PROMPT_VERSION = "2.0.0"

# Valid categories
VALID_CATEGORIES = [
    "Ciencia", "Cultura", "Deportes", "Economía", "Educación",
    "Investigación", "Medio Ambiente", "Política", "Salud",
    "Sociedad", "Tecnología", "Turismo"
]


@router.post("/{item_id}/process-ai")
async def process_item_with_ai(
    item_id: uuid.UUID,
    current_user: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Process a scraping item with AI to generate:
    - Improved title
    - Summary
    - Category and tags
    - Three reading levels (sin_vueltas, lo_central, en_profundidad)

    **Requires:** Admin authentication

    This is the on-demand version of the batch AI processing script.
    """
    if not OPENAI_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="AI processing not available. OpenAI library not installed."
        )

    if not openai_client:
        raise HTTPException(
            status_code=503,
            detail="AI processing not available. OPENAI_API_KEY not configured."
        )

    # Get scraping item
    query = select(ScrapingItem).where(ScrapingItem.id == item_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Scraping item not found")

    # Check if item has content to process
    if not item.content:
        raise HTTPException(
            status_code=400,
            detail="Item must have content to process with AI"
        )

    start_time = time.time()

    try:
        # Create the processing prompt
        categories_str = ", ".join(VALID_CATEGORIES)

        prompt = f"""Eres un editor periodístico profesional de "La Data Justa", un medio innovador que ofrece tres niveles de profundidad para cada noticia.

Analiza el siguiente artículo y genera:

1. **Título mejorado**: Versión más atractiva y periodística, máximo 100 caracteres
2. **Resumen**: Resumen conciso para lista de noticias (150-200 caracteres)
3. **Sin vueltas**: Ultra breve, 1-2 oraciones directas (40-60 palabras)
4. **Lo central**: Párrafo esencial con lo más importante (80-120 palabras)
5. **En profundidad**: Versión completa con contexto y detalles (200-300 palabras)
6. **Categoría**: Una sola de: {categories_str}
7. **Tags**: 3-5 etiquetas relevantes
8. **Validación**: ¿Es contenido relevante y publicable?

ARTÍCULO ORIGINAL:
---
Título: {item.title or 'Sin título'}
Resumen: {item.summary or 'Sin resumen'}
Sección: {item.source_section or 'Sin sección'}

Contenido:
{item.content[:3000] if item.content else ''}
---

Responde SOLO con un JSON válido en este formato exacto:
{{
    "title": "título mejorado aquí",
    "summary": "resumen para lista",
    "sin_vueltas": "1-2 oraciones ultra directas",
    "lo_central": "párrafo esencial con lo más importante",
    "en_profundidad": "versión completa con contexto y análisis",
    "category": "categoría aquí",
    "tags": ["tag1", "tag2", "tag3"],
    "is_valid": true,
    "validation_reason": "explicación si is_valid es false"
}}"""

        # Call OpenAI API
        response = await openai_client.chat.completions.create(
            model=OPENAI_TEXT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Eres un editor periodístico profesional. Respondes solo con JSON válido."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=1500,
            response_format={"type": "json_object"}
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # Parse AI response
        ai_content = response.choices[0].message.content
        ai_data = json.loads(ai_content)

        # Calculate tokens and cost
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        # gpt-4o-mini pricing: Input $0.150/1M, Output $0.600/1M
        cost_usd = Decimal(str((input_tokens * 0.150 / 1_000_000) + (output_tokens * 0.600 / 1_000_000)))

        # Determine new status
        is_valid = ai_data.get("is_valid", True)
        if is_valid:
            new_status = "ai_completed"
            status_message = "AI processing completed successfully"
        else:
            new_status = "discarded"
            status_message = f"Discarded: {ai_data.get('validation_reason', 'Not valid')}"

        # Update item in database
        item.ai_title = ai_data.get("title")
        item.ai_summary = ai_data.get("summary")
        item.ai_category = ai_data.get("category")
        item.ai_tags = ai_data.get("tags", [])
        item.ai_model = OPENAI_TEXT_MODEL
        item.ai_prompt_version = AI_PROMPT_VERSION
        item.ai_tokens_used = total_tokens
        item.ai_cost_usd = cost_usd
        item.ai_processed_at = datetime.utcnow()
        item.ai_processing_duration_ms = duration_ms
        item.ai_metadata = {
            "is_valid": is_valid,
            "validation_reason": ai_data.get("validation_reason"),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "sin_vueltas": ai_data.get("sin_vueltas"),
            "lo_central": ai_data.get("lo_central"),
            "en_profundidad": ai_data.get("en_profundidad"),
        }
        item.status = new_status
        item.status_message = status_message

        await db.commit()
        await db.refresh(item)

        return {
            "success": True,
            "status": new_status,
            "ai_title": ai_data.get("title"),
            "ai_summary": ai_data.get("summary"),
            "ai_category": ai_data.get("category"),
            "ai_tags": ai_data.get("tags", []),
            "reading_levels": {
                "sin_vueltas": ai_data.get("sin_vueltas"),
                "lo_central": ai_data.get("lo_central"),
                "en_profundidad": ai_data.get("en_profundidad"),
            },
            "tokens_used": total_tokens,
            "cost_usd": float(cost_usd),
            "duration_ms": duration_ms,
            "is_valid": is_valid,
            "validation_reason": ai_data.get("validation_reason") if not is_valid else None
        }

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse AI response as JSON: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI processing failed: {str(e)}"
        )


# ===== IMAGE GENERATION (ANTI-CLICKBAIT) =====

@router.get("/visual-states")
async def get_visual_states() -> dict:
    """
    Get available visual states for anti-clickbait image generation.

    Returns the list of visual states with their names and descriptions.
    """
    return {
        "states": {
            key: {
                "name": value["name"],
                "description": value["description"]
            }
            for key, value in VISUAL_STATES.items()
        }
    }


@router.post("/{item_id}/generate-anticlickbait-image")
async def generate_anticlickbait_image(
    item_id: uuid.UUID,
    current_user: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
    visual_state: str = Query(
        default="estabilidad",
        description="Visual state for the image: incertidumbre, tension, impacto, estabilidad, cierre"
    ),
) -> dict:
    """
    Generate an anti-clickbait editorial image for a scraping item.

    **Requires:** Admin authentication

    This endpoint generates abstract, minimalist images that reflect the
    *information state* of the news, not the story itself.

    Visual states:
    - **incertidumbre**: Something not yet defined
    - **tension**: Opposing forces, negotiation, moderate conflict
    - **impacto**: Important decision, ruling, strong announcement
    - **estabilidad**: Normality, continuity, data without surprises
    - **cierre**: Issue that resolves or cools down

    The images are designed to be:
    - Abstract and minimalist
    - No text, no people, no scenes
    - Sober, professional colors
    - Simple forms (lines, blocks, balance)
    - Consistent visual identity for La Data Justa
    """
    if not OPENAI_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Image generation service not available. OpenAI library not installed."
        )

    if not openai_client:
        raise HTTPException(
            status_code=503,
            detail="Image generation service not available. OPENAI_API_KEY not configured."
        )

    # Validate visual state
    if visual_state not in VISUAL_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid visual_state. Must be one of: {', '.join(VISUAL_STATES.keys())}"
        )

    # Get scraping item
    query = select(ScrapingItem).where(ScrapingItem.id == item_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Scraping item not found")

    # Verify item has AI-processed content
    if not item.ai_title or not item.ai_category:
        raise HTTPException(
            status_code=400,
            detail="Item must be AI-processed before generating image (ai_title and ai_category required)"
        )

    # Generate image with DALL-E
    start_time = time.time()

    try:
        # Get visual state configuration
        state_config = VISUAL_STATES[visual_state]

        # Build the anti-clickbait prompt
        image_prompt = f"""{ANTICLICKBAIT_BASE_PROMPT}

VISUAL STATE: {state_config['name'].upper()} - {state_config['description']}

SPECIFIC VISUAL ELEMENTS FOR THIS STATE:
{state_config['prompt_elements']}

NEWS CATEGORY (for subtle color/mood influence only, NOT for depicting scenes): {item.ai_category}

CRITICAL: The image must NOT illustrate the news story. It should only convey the emotional/informational STATE through abstract geometric composition."""

        # Truncate if too long (DALL-E has a limit)
        if len(image_prompt) > 4000:
            image_prompt = image_prompt[:4000]

        # Call DALL-E API
        response = await openai_client.images.generate(
            model=DALLE_MODEL,
            prompt=image_prompt,
            size=DALLE_SIZE,
            quality=DALLE_QUALITY,
            n=1
        )

        duration_ms = int((time.time() - start_time) * 1000)

        temp_image_url = response.data[0].url
        revised_prompt = response.data[0].revised_prompt

        # Download and save image permanently
        filename = f"{item_id}_anticlickbait_{visual_state}_{int(time.time())}.png"
        permanent_url = await download_and_save_image(temp_image_url, filename)

        # Calculate cost (as Decimal to match database type)
        cost_usd = Decimal("0.080") if DALLE_QUALITY == "hd" else Decimal("0.040")

        # Update item in database with permanent URL
        item.image_urls = [permanent_url]

        # Update ai_metadata with image generation info
        if not item.ai_metadata:
            item.ai_metadata = {}

        item.ai_metadata["image_generation"] = {
            "type": "anticlickbait",
            "visual_state": visual_state,
            "visual_state_name": state_config["name"],
            "model": DALLE_MODEL,
            "size": DALLE_SIZE,
            "quality": DALLE_QUALITY,
            "revised_prompt": revised_prompt,
            "cost_usd": float(cost_usd),
            "duration_ms": duration_ms,
            "generated_at": datetime.utcnow().isoformat()
        }

        # Add cost to total AI cost if available
        if item.ai_cost_usd:
            item.ai_cost_usd += cost_usd
        else:
            item.ai_cost_usd = cost_usd

        await db.commit()

        return {
            "success": True,
            "image_url": permanent_url,
            "visual_state": visual_state,
            "visual_state_name": state_config["name"],
            "revised_prompt": revised_prompt,
            "metadata": {
                "type": "anticlickbait",
                "model": DALLE_MODEL,
                "size": DALLE_SIZE,
                "quality": DALLE_QUALITY,
                "cost_usd": float(cost_usd),
                "duration_ms": duration_ms,
                "filename": filename
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate anti-clickbait image: {str(e)}"
        )


# Legacy endpoint for backwards compatibility
@router.post("/{item_id}/generate-image")
async def generate_item_image(
    item_id: uuid.UUID,
    current_user: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Legacy endpoint - redirects to anti-clickbait image generation with 'estabilidad' state.
    Use /generate-anticlickbait-image for full control over visual states.
    """
    return await generate_anticlickbait_image(
        item_id=item_id,
        current_user=current_user,
        db=db,
        visual_state="estabilidad"
    )


# ===== TYPOGRAPHIC COVER IMAGE GENERATION =====
# Simple, editorial cover images with 1-3 keywords

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Category color scheme (subtle, editorial)
CATEGORY_COLORS = {
    "Política": {"bg": "#1e293b", "text": "#818cf8", "accent": "#6366f1"},
    "Economía": {"bg": "#1c1917", "text": "#22c55e", "accent": "#16a34a"},
    "Sociedad": {"bg": "#1e1b4b", "text": "#f59e0b", "accent": "#d97706"},
    "Deportes": {"bg": "#1f2937", "text": "#ef4444", "accent": "#dc2626"},
    "Tecnología": {"bg": "#0c1929", "text": "#06b6d4", "accent": "#0891b2"},
    "Cultura": {"bg": "#1e1b2e", "text": "#a78bfa", "accent": "#8b5cf6"},
    "Salud": {"bg": "#1a2e1a", "text": "#4ade80", "accent": "#22c55e"},
    "Ciencia": {"bg": "#0f172a", "text": "#38bdf8", "accent": "#0284c7"},
    "Educación": {"bg": "#1e293b", "text": "#f472b6", "accent": "#db2777"},
    "Medio Ambiente": {"bg": "#052e16", "text": "#4ade80", "accent": "#16a34a"},
    "Investigación": {"bg": "#1e1b4b", "text": "#c4b5fd", "accent": "#7c3aed"},
    "Turismo": {"bg": "#1e3a5f", "text": "#f97316", "accent": "#ea580c"},
    "default": {"bg": "#1e293b", "text": "#94a3b8", "accent": "#64748b"},
}


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def generate_typographic_cover(
    keywords: list[str],
    category: str,
    item_id: str,
) -> str:
    """
    Generate a simple typographic cover image with 1-3 keywords.
    Returns the file path of the saved image.
    """
    colors = CATEGORY_COLORS.get(category, CATEGORY_COLORS["default"])
    bg_color = hex_to_rgb(colors["bg"])
    text_color = hex_to_rgb(colors["text"])
    accent_color = hex_to_rgb(colors["accent"])

    width, height = 1200, 630
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Try to load fonts
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    main_font = None
    small_font = None
    for font_path in font_paths:
        if Path(font_path).exists():
            main_font = ImageFont.truetype(font_path, 80)
            small_font = ImageFont.truetype(font_path, 16)
            break

    if not main_font:
        main_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Prepare text lines
    text_lines = [kw.upper() for kw in keywords[:3]]

    # Calculate dimensions for centering
    line_spacing = 100
    total_text_height = len(text_lines) * line_spacing
    y_start = (height - total_text_height) // 2

    # Draw each line centered
    for i, line in enumerate(text_lines):
        bbox = draw.textbbox((0, 0), line, font=main_font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        y = y_start + (i * line_spacing)
        draw.text((x, y), line, fill=text_color, font=main_font)

    # Accent line at bottom
    line_y = height - 50
    line_width = 200
    line_x = (width - line_width) // 2
    draw.line([(line_x, line_y), (line_x + line_width, line_y)], fill=accent_color, width=4)

    # Branding
    brand = "LA DATA JUSTA"
    brand_bbox = draw.textbbox((0, 0), brand, font=small_font)
    brand_w = brand_bbox[2] - brand_bbox[0]
    draw.text((width - brand_w - 30, height - 40), brand, fill=accent_color, font=small_font)

    # Save
    filename = f"{item_id}_cover_{int(time.time())}.png"
    filepath = IMAGE_DIR / filename
    img.save(filepath, "PNG", optimize=True)

    return f"{IMAGE_URL_PREFIX}/{filename}"


def extract_keywords_from_title(title: str) -> list[str]:
    """Extract 1-3 key words from a title."""
    if not title:
        return ["NOTICIA"]

    import re

    stopwords = {
        "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "en",
        "por", "para", "con", "sin", "sobre", "tras", "ante", "bajo", "desde",
        "hasta", "hacia", "entre", "contra", "según", "y", "o", "que", "se",
        "su", "sus", "al", "es", "son", "fue", "han", "ha", "hay", "como", "más",
        "ya", "pero", "si", "no", "le", "les", "lo", "a", "este", "esta", "esto",
        "ese", "esa", "eso", "aquel", "cada", "todo", "toda", "todos", "todas",
        "muy", "mucho", "poco", "algo", "nada", "mismo", "misma", "otro", "otra",
        "qué", "quién", "cuál", "cuándo", "dónde", "cómo", "porque", "pues",
        "así", "también", "solo", "sólo", "ahora", "hoy", "ayer", "mañana",
        "siempre", "nunca", "después", "antes", "luego", "mientras", "cuando",
        "aunque", "ni", "entonces", "ser", "estar"
    }

    words = re.findall(r"\b[a-záéíóúñü]+\b", title.lower())
    keywords = [w for w in words if w not in stopwords and len(w) > 3]
    keywords = sorted(set(keywords), key=lambda x: (-len(x), keywords.index(x) if x in keywords else 999))[:3]

    if not keywords:
        words = title.upper().split()[:3]
        keywords = [w.strip(".,;:!?¿¡()[]{}\"'") for w in words if len(w) > 2]

    return keywords if keywords else ["NOTICIA"]


@router.post("/{item_id}/generate-cover")
async def generate_cover_image(
    item_id: uuid.UUID,
    current_user: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
    keywords: str = Query(
        default=None,
        description="Comma-separated keywords (1-3 words). If not provided, extracted from title."
    ),
) -> dict:
    """
    Generate a typographic cover image for a scraping item.

    **Requires:** Admin authentication

    Creates simple, editorial cover images with 1-3 keywords.
    Uses large uppercase text on a category-colored background.
    """
    if not PIL_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Image generation not available. Pillow library not installed."
        )

    query = select(ScrapingItem).where(ScrapingItem.id == item_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Scraping item not found")

    if not item.ai_title:
        raise HTTPException(
            status_code=400,
            detail="Item must be AI-processed before generating cover"
        )

    start_time = time.time()

    if keywords:
        keyword_list = [kw.strip() for kw in keywords.split(",") if kw.strip()][:3]
    else:
        keyword_list = extract_keywords_from_title(item.ai_title)

    try:
        image_url = generate_typographic_cover(
            keywords=keyword_list,
            category=item.ai_category or "default",
            item_id=str(item_id),
        )

        duration_ms = int((time.time() - start_time) * 1000)

        item.image_urls = [image_url]

        if not item.ai_metadata:
            item.ai_metadata = {}

        item.ai_metadata["cover_generation"] = {
            "type": "typographic",
            "keywords": keyword_list,
            "category": item.ai_category,
            "duration_ms": duration_ms,
            "generated_at": datetime.utcnow().isoformat()
        }
        item.ai_metadata["cover_keywords"] = keyword_list

        await db.commit()

        return {
            "success": True,
            "image_url": image_url,
            "keywords": keyword_list,
            "category": item.ai_category,
            "metadata": {
                "type": "typographic",
                "duration_ms": duration_ms,
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate cover image: {str(e)}"
        )


@router.get("/{item_id}/suggest-keywords")
async def suggest_cover_keywords(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Suggest keywords for a cover image based on the item's title."""
    query = select(ScrapingItem).where(ScrapingItem.id == item_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Scraping item not found")

    if not item.ai_title:
        raise HTTPException(status_code=400, detail="Item must be AI-processed")

    saved_keywords = None
    if item.ai_metadata and "cover_keywords" in item.ai_metadata:
        saved_keywords = item.ai_metadata["cover_keywords"]

    suggested = extract_keywords_from_title(item.ai_title)

    return {
        "suggested_keywords": suggested,
        "saved_keywords": saved_keywords,
        "title": item.ai_title,
        "category": item.ai_category,
    }


# ===== DEBUG ENDPOINT (TEMPORARY) =====

@router.get("/debug/code-version")
async def debug_code_version() -> dict:
    """
    Temporary endpoint to verify code is loaded correctly.
    Returns a version indicator that changes when code is updated.
    """
    import inspect

    # Get the publish function source to verify it has the new code
    publish_func = inspect.getsource(publish_scraping_item)
    has_content_migration = "content_sin_vueltas" in publish_func and "ai_metadata.get" in publish_func

    return {
        "code_version": "2026-01-29-v2",
        "has_content_migration_code": has_content_migration,
        "publish_function_lines": len(publish_func.split("\n")),
        "message": "Si has_content_migration_code es True, el codigo esta actualizado"
    }
