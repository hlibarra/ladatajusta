"""
Scraping Sources Management API
CRUD operations for scraping source configurations
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal

from app.db.session import get_db
from app.db.models import ScrapingSource
from app.api.deps import get_current_user, CurrentAdmin

router = APIRouter()


# Schemas
class ScrapingSourceBase(BaseModel):
    name: str
    slug: str
    media_type: str
    is_active: bool = False
    scraper_type: str = "web"
    base_url: str
    sections_to_scrape: Optional[List[str]] = None
    scraping_interval_minutes: Optional[int] = 60
    max_articles_per_run: Optional[int] = 50
    scraper_script_path: Optional[str] = None
    scraper_config: Optional[dict] = None
    ai_prompt: Optional[str] = None
    auto_publish: bool = False
    auto_publish_delay_minutes: int = 15
    notes: Optional[str] = None


class ScrapingSourceCreate(ScrapingSourceBase):
    pass


class ScrapingSourceUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    scraper_type: Optional[str] = None
    base_url: Optional[str] = None
    sections_to_scrape: Optional[List[str]] = None
    scraping_interval_minutes: Optional[int] = None
    max_articles_per_run: Optional[int] = None
    scraper_script_path: Optional[str] = None
    scraper_config: Optional[dict] = None
    ai_prompt: Optional[str] = None
    auto_publish: Optional[bool] = None
    auto_publish_delay_minutes: Optional[int] = None
    max_consecutive_errors: Optional[int] = None
    notes: Optional[str] = None


class ScrapingSourceResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    media_type: str
    is_active: bool
    scraper_type: str
    base_url: str
    sections_to_scrape: Optional[List[str]]
    scraping_interval_minutes: Optional[int]
    max_articles_per_run: Optional[int]
    scraper_script_path: Optional[str]
    scraper_config: Optional[dict]
    ai_prompt: Optional[str]
    auto_publish: bool
    auto_publish_delay_minutes: int
    last_scraped_at: Optional[datetime]
    last_scrape_status: Optional[str]
    last_scrape_message: Optional[str]
    last_scrape_items_count: int
    total_items_scraped: int
    total_scrape_runs: int
    success_rate: Optional[Decimal]
    consecutive_errors: int
    max_consecutive_errors: int
    created_at: datetime
    updated_at: datetime
    notes: Optional[str]

    class Config:
        from_attributes = True


# Routes
@router.get("", response_model=List[ScrapingSourceResponse])
async def list_scraping_sources(
    active_only: bool = False,
    session: AsyncSession = Depends(get_db),
    _current_user = Depends(get_current_user)
):
    """List all scraping sources"""
    query = select(ScrapingSource)

    if active_only:
        query = query.where(ScrapingSource.is_active == True)

    query = query.order_by(ScrapingSource.name)

    result = await session.execute(query)
    sources = result.scalars().all()

    return sources


@router.get("/{source_id}", response_model=ScrapingSourceResponse)
async def get_scraping_source(
    source_id: UUID,
    session: AsyncSession = Depends(get_db),
    _current_user = Depends(get_current_user)
):
    """Get a specific scraping source"""
    result = await session.execute(
        select(ScrapingSource).where(ScrapingSource.id == source_id)
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="Scraping source not found")

    return source


@router.post("", response_model=ScrapingSourceResponse)
async def create_scraping_source(
    source_data: ScrapingSourceCreate,
    current_user: CurrentAdmin,
    session: AsyncSession = Depends(get_db)
):
    """Create a new scraping source (admin only)"""

    # Check if slug or media_type already exists
    existing = await session.execute(
        select(ScrapingSource).where(
            (ScrapingSource.slug == source_data.slug) |
            (ScrapingSource.media_type == source_data.media_type)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="A source with this slug or media_type already exists"
        )

    source = ScrapingSource(
        **source_data.model_dump(),
        created_by=current_user.email
    )

    session.add(source)
    await session.commit()
    await session.refresh(source)

    return source


@router.patch("/{source_id}", response_model=ScrapingSourceResponse)
async def update_scraping_source(
    source_id: UUID,
    source_data: ScrapingSourceUpdate,
    current_user: CurrentAdmin,
    session: AsyncSession = Depends(get_db)
):
    """Update a scraping source (admin only)"""

    result = await session.execute(
        select(ScrapingSource).where(ScrapingSource.id == source_id)
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="Scraping source not found")

    # Update fields
    update_data = source_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(source, field, value)

    source.updated_by = current_user.email

    await session.commit()
    await session.refresh(source)

    return source


@router.delete("/{source_id}")
async def delete_scraping_source(
    source_id: UUID,
    current_user: CurrentAdmin,
    session: AsyncSession = Depends(get_db)
):
    """Delete a scraping source (admin only)"""

    result = await session.execute(
        select(ScrapingSource).where(ScrapingSource.id == source_id)
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="Scraping source not found")

    await session.delete(source)
    await session.commit()

    return {"message": "Scraping source deleted successfully"}


@router.post("/{source_id}/toggle")
async def toggle_scraping_source(
    source_id: UUID,
    current_user: CurrentAdmin,
    session: AsyncSession = Depends(get_db)
):
    """Toggle active status of a scraping source (admin only)"""

    result = await session.execute(
        select(ScrapingSource).where(ScrapingSource.id == source_id)
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="Scraping source not found")

    source.is_active = not source.is_active
    source.updated_by = current_user.email

    await session.commit()
    await session.refresh(source)

    return {
        "message": f"Source {'activated' if source.is_active else 'deactivated'}",
        "is_active": source.is_active
    }


@router.get("/stats")
async def get_scraping_sources_stats(
    session: AsyncSession = Depends(get_db),
    _current_user = Depends(get_current_user)
):
    """Get overall statistics for scraping sources"""

    result = await session.execute(
        select(
            func.count(ScrapingSource.id).label("total_sources"),
            func.count(ScrapingSource.id).filter(ScrapingSource.is_active == True).label("active_sources"),
            func.sum(ScrapingSource.total_items_scraped).label("total_items"),
            func.sum(ScrapingSource.total_scrape_runs).label("total_runs"),
        )
    )

    stats = result.one()

    return {
        "total_sources": stats.total_sources or 0,
        "active_sources": stats.active_sources or 0,
        "total_items_scraped": stats.total_items or 0,
        "total_scrape_runs": stats.total_runs or 0,
    }
