from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentAdmin
from app.db.models import AIRun, Publication, RSSFeed, ScrapedArticle, Vote
from app.db.session import get_db

router = APIRouter()


class SourceCount(BaseModel):
    source_name: str
    count: int


class DashboardStats(BaseModel):
    total_publications: int
    by_state: dict[str, int]
    by_source: list[SourceCount]
    ai_runs_today: int
    ai_errors_today: int
    recent_votes: dict[str, int]
    feeds_status: dict[str, int]


class VoteTotals(BaseModel):
    publication_id: uuid.UUID
    hot: int
    cold: int


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    # Total publications
    total = await db.scalar(select(func.count()).select_from(Publication)) or 0

    # By state
    state_counts = await db.execute(
        select(Publication.state, func.count()).group_by(Publication.state)
    )
    by_state = {row[0]: row[1] for row in state_counts}

    # By source (from scraped articles)
    source_counts = await db.execute(
        select(ScrapedArticle.source_name, func.count())
        .join(Publication, Publication.scraped_article_id == ScrapedArticle.id)
        .group_by(ScrapedArticle.source_name)
        .order_by(func.count().desc())
        .limit(10)
    )
    by_source = [SourceCount(source_name=row[0], count=row[1]) for row in source_counts]

    # AI runs today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    ai_runs_today = await db.scalar(
        select(func.count()).select_from(AIRun).where(AIRun.created_at >= today_start)
    ) or 0

    # AI errors today
    ai_errors_today = await db.scalar(
        select(func.count())
        .select_from(AIRun)
        .where(AIRun.created_at >= today_start, AIRun.status != "ok")
    ) or 0

    # Recent votes (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    hot_votes = await db.scalar(
        select(func.count())
        .select_from(Vote)
        .where(Vote.created_at >= week_ago, Vote.vote_type == "hot")
    ) or 0
    cold_votes = await db.scalar(
        select(func.count())
        .select_from(Vote)
        .where(Vote.created_at >= week_ago, Vote.vote_type == "cold")
    ) or 0
    recent_votes = {"hot": hot_votes, "cold": cold_votes}

    # Feeds status
    active_feeds = await db.scalar(
        select(func.count()).select_from(RSSFeed).where(RSSFeed.is_active == True)
    ) or 0
    feeds_with_errors = await db.scalar(
        select(func.count()).select_from(RSSFeed).where(RSSFeed.error_count > 0)
    ) or 0
    feeds_status = {"active": active_feeds, "with_errors": feeds_with_errors}

    return DashboardStats(
        total_publications=total,
        by_state=by_state,
        by_source=by_source,
        ai_runs_today=ai_runs_today,
        ai_errors_today=ai_errors_today,
        recent_votes=recent_votes,
        feeds_status=feeds_status,
    )


@router.get("/votes/{publication_id}", response_model=VoteTotals)
async def get_vote_totals(
    publication_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> VoteTotals:
    hot = await db.scalar(
        select(func.count()).select_from(Vote).where(Vote.publication_id == publication_id, Vote.vote_type == "hot")
    )
    cold = await db.scalar(
        select(func.count()).select_from(Vote).where(Vote.publication_id == publication_id, Vote.vote_type == "cold")
    )

    return VoteTotals(publication_id=publication_id, hot=int(hot or 0), cold=int(cold or 0))
