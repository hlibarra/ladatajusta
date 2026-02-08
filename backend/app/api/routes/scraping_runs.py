from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta

from app.api.deps import get_current_user
from app.api.schemas import (
    ScrapingRunOut,
    ScrapingRunList,
    ScrapingRunStats,
    ScrapingRunUpdate
)
from app.db.session import get_db
from app.db.models import ScrapingRun, ScrapingItem, User

router = APIRouter()


@router.get("/", response_model=ScrapingRunList)
async def list_scraping_runs(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None, pattern="^(running|completed|failed|cancelled)$"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    source_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List scraping runs with pagination and optional filters.
    Returns runs ordered by started_at descending (most recent first).
    Filters: status, date_from, date_to, source_id
    """
    # Build query
    query = select(ScrapingRun).order_by(desc(ScrapingRun.started_at))

    # Apply filters
    if status:
        query = query.where(ScrapingRun.status == status)

    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.fromisoformat(date_from)
            query = query.where(ScrapingRun.started_at >= date_from_obj)
        except ValueError:
            pass  # Invalid date format, ignore filter

    if date_to:
        try:
            from datetime import datetime, timedelta
            date_to_obj = datetime.fromisoformat(date_to) + timedelta(days=1)  # Include entire day
            query = query.where(ScrapingRun.started_at < date_to_obj)
        except ValueError:
            pass  # Invalid date format, ignore filter

    if source_id:
        # Filter by source - check if source_id is in the sources_processed array
        query = query.where(ScrapingRun.sources_processed.contains([source_id]))

    # Get total count with same filters
    count_query = select(func.count()).select_from(ScrapingRun)
    if status:
        count_query = count_query.where(ScrapingRun.status == status)
    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.fromisoformat(date_from)
            count_query = count_query.where(ScrapingRun.started_at >= date_from_obj)
        except ValueError:
            pass
    if date_to:
        try:
            from datetime import datetime, timedelta
            date_to_obj = datetime.fromisoformat(date_to) + timedelta(days=1)
            count_query = count_query.where(ScrapingRun.started_at < date_to_obj)
        except ValueError:
            pass
    if source_id:
        count_query = count_query.where(ScrapingRun.sources_processed.contains([source_id]))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    runs = result.scalars().all()

    return ScrapingRunList(
        runs=runs,
        total=total,
        offset=offset,
        limit=limit
    )


@router.get("/stats", response_model=ScrapingRunStats)
async def get_scraping_runs_stats(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get statistics for scraping runs.
    By default shows stats for the last 30 days.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Get stats
    stats_query = select(
        func.count(ScrapingRun.id).label('total_runs'),
        func.count(ScrapingRun.id).filter(ScrapingRun.status == 'completed').label('completed_runs'),
        func.count(ScrapingRun.id).filter(ScrapingRun.status == 'failed').label('failed_runs'),
        func.sum(ScrapingRun.items_scraped).label('total_items_scraped'),
        func.sum(ScrapingRun.items_failed).label('total_items_failed'),
        func.avg(ScrapingRun.duration_seconds).label('avg_duration_seconds'),
        func.max(ScrapingRun.started_at).label('last_run_at')
    ).where(ScrapingRun.started_at >= cutoff_date)

    result = await db.execute(stats_query)
    row = result.one()

    return ScrapingRunStats(
        total_runs=row.total_runs or 0,
        completed_runs=row.completed_runs or 0,
        failed_runs=row.failed_runs or 0,
        total_items_scraped=row.total_items_scraped or 0,
        total_items_failed=row.total_items_failed or 0,
        avg_duration_seconds=float(row.avg_duration_seconds) if row.avg_duration_seconds else None,
        last_run_at=row.last_run_at
    )


@router.get("/{run_id}", response_model=ScrapingRunOut)
async def get_scraping_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get details of a specific scraping run by ID.
    """
    query = select(ScrapingRun).where(ScrapingRun.id == run_id)
    result = await db.execute(query)
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Scraping run not found")

    return run


@router.get("/{run_id}/items")
async def get_scraping_run_items(
    run_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get items scraped during a specific run.
    """
    # Verify run exists
    run_query = select(ScrapingRun).where(ScrapingRun.id == run_id)
    run_result = await db.execute(run_query)
    run = run_result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Scraping run not found")

    # Get items for this run
    query = (
        select(ScrapingItem)
        .where(ScrapingItem.scraping_run_id == run_id)
        .order_by(desc(ScrapingItem.scraped_at))
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(query)
    items = result.scalars().all()

    # Get total count
    count_query = select(func.count()).select_from(ScrapingItem).where(ScrapingItem.scraping_run_id == run_id)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit
    }


@router.patch("/{run_id}", response_model=ScrapingRunOut)
async def update_scraping_run(
    run_id: str,
    update_data: ScrapingRunUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a scraping run (mainly used by the scraper service to update status/results).
    """
    query = select(ScrapingRun).where(ScrapingRun.id == run_id)
    result = await db.execute(query)
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Scraping run not found")

    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(run, key, value)

    await db.commit()
    await db.refresh(run)

    return run
