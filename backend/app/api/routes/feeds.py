from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentAdmin
from app.db.models import RSSFeed
from app.db.session import get_db

router = APIRouter()


class FeedCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    url: str = Field(..., min_length=10, max_length=2048)
    fetch_interval_minutes: int = Field(default=60, ge=5, le=1440)


class FeedUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    is_active: bool | None = None
    fetch_interval_minutes: int | None = Field(default=None, ge=5, le=1440)


class FeedOut(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    is_active: bool
    last_fetched_at: datetime | None
    fetch_interval_minutes: int
    error_count: int
    last_error: str | None
    created_at: datetime


@router.get("/", response_model=list[FeedOut])
async def list_feeds(
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> list[FeedOut]:
    q = select(RSSFeed).order_by(RSSFeed.created_at.desc())
    rows = (await db.scalars(q)).all()
    return [
        FeedOut(
            id=f.id,
            name=f.name,
            url=f.url,
            is_active=f.is_active,
            last_fetched_at=f.last_fetched_at,
            fetch_interval_minutes=f.fetch_interval_minutes,
            error_count=f.error_count,
            last_error=f.last_error,
            created_at=f.created_at,
        )
        for f in rows
    ]


@router.post("/", response_model=FeedOut, status_code=status.HTTP_201_CREATED)
async def create_feed(
    payload: FeedCreate,
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> FeedOut:
    existing = await db.scalar(select(RSSFeed).where(RSSFeed.url == payload.url))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un feed con esta URL",
        )

    feed = RSSFeed(
        name=payload.name,
        url=payload.url,
        fetch_interval_minutes=payload.fetch_interval_minutes,
    )
    db.add(feed)
    await db.commit()
    await db.refresh(feed)

    return FeedOut(
        id=feed.id,
        name=feed.name,
        url=feed.url,
        is_active=feed.is_active,
        last_fetched_at=feed.last_fetched_at,
        fetch_interval_minutes=feed.fetch_interval_minutes,
        error_count=feed.error_count,
        last_error=feed.last_error,
        created_at=feed.created_at,
    )


@router.get("/{feed_id}", response_model=FeedOut)
async def get_feed(
    feed_id: uuid.UUID,
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> FeedOut:
    feed = await db.get(RSSFeed, feed_id)
    if not feed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed no encontrado")

    return FeedOut(
        id=feed.id,
        name=feed.name,
        url=feed.url,
        is_active=feed.is_active,
        last_fetched_at=feed.last_fetched_at,
        fetch_interval_minutes=feed.fetch_interval_minutes,
        error_count=feed.error_count,
        last_error=feed.last_error,
        created_at=feed.created_at,
    )


@router.put("/{feed_id}", response_model=FeedOut)
async def update_feed(
    feed_id: uuid.UUID,
    payload: FeedUpdate,
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> FeedOut:
    feed = await db.get(RSSFeed, feed_id)
    if not feed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed no encontrado")

    if payload.name is not None:
        feed.name = payload.name
    if payload.url is not None:
        existing = await db.scalar(select(RSSFeed).where(RSSFeed.url == payload.url, RSSFeed.id != feed_id))
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ya existe un feed con esta URL")
        feed.url = payload.url
    if payload.is_active is not None:
        feed.is_active = payload.is_active
    if payload.fetch_interval_minutes is not None:
        feed.fetch_interval_minutes = payload.fetch_interval_minutes

    await db.commit()
    await db.refresh(feed)

    return FeedOut(
        id=feed.id,
        name=feed.name,
        url=feed.url,
        is_active=feed.is_active,
        last_fetched_at=feed.last_fetched_at,
        fetch_interval_minutes=feed.fetch_interval_minutes,
        error_count=feed.error_count,
        last_error=feed.last_error,
        created_at=feed.created_at,
    )


@router.delete("/{feed_id}")
async def delete_feed(
    feed_id: uuid.UUID,
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> Response:
    feed = await db.get(RSSFeed, feed_id)
    if not feed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed no encontrado")

    await db.delete(feed)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{feed_id}/fetch", response_model=FeedOut)
async def trigger_fetch(
    feed_id: uuid.UUID,
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> FeedOut:
    feed = await db.get(RSSFeed, feed_id)
    if not feed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed no encontrado")

    # Mark as needing fetch by setting last_fetched_at to None
    feed.last_fetched_at = None
    await db.commit()
    await db.refresh(feed)

    return FeedOut(
        id=feed.id,
        name=feed.name,
        url=feed.url,
        is_active=feed.is_active,
        last_fetched_at=feed.last_fetched_at,
        fetch_interval_minutes=feed.fetch_interval_minutes,
        error_count=feed.error_count,
        last_error=feed.last_error,
        created_at=feed.created_at,
    )
