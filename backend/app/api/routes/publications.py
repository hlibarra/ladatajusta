from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.pipeline import process_article
from app.api.schemas import PublicationOut, VoteRequest, VoteTotalsOut
from app.db.models import AIRun, Publication, ScrapedArticle, Vote
from app.db.session import get_db

router = APIRouter()


def _voter_key(req: Request) -> str:
    ip = req.client.host if req.client else "unknown"
    ua = req.headers.get("user-agent", "")
    raw = f"{ip}|{ua}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@router.get("/", response_model=list[PublicationOut])
async def list_publications(
    db: AsyncSession = Depends(get_db),
    state: str = "published",
    limit: int = 30,
    offset: int = 0,
) -> list[PublicationOut]:
    q = (
        select(Publication)
        .where(Publication.state == state)
        .order_by(Publication.published_at.desc().nullslast(), Publication.created_at.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    rows = (await db.scalars(q)).all()
    return [
        PublicationOut(
            id=r.id,
            state=r.state,
            title=r.title,
            summary=r.summary,
            body=r.body,
            category=r.category,
            tags=r.tags or [],
            created_at=r.created_at,
            published_at=r.published_at,
        )
        for r in rows
    ]


@router.get("/{publication_id}", response_model=PublicationOut)
async def get_publication(publication_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> PublicationOut:
    pub = await db.get(Publication, publication_id)
    if not pub:
        raise HTTPException(status_code=404, detail="No existe")
    return PublicationOut(
        id=pub.id,
        state=pub.state,
        title=pub.title,
        summary=pub.summary,
        body=pub.body,
        category=pub.category,
        tags=pub.tags or [],
        created_at=pub.created_at,
        published_at=pub.published_at,
    )


@router.post("/process/{scraped_id}", response_model=PublicationOut)
async def process_scraped(scraped_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> PublicationOut:
    article = await db.get(ScrapedArticle, scraped_id)
    if not article:
        raise HTTPException(status_code=404, detail="ScrapedArticle no existe")

    # if already processed
    existing_pub = await db.scalar(select(Publication).where(Publication.scraped_article_id == scraped_id))
    if existing_pub:
        return PublicationOut(
            id=existing_pub.id,
            state=existing_pub.state,
            title=existing_pub.title,
            summary=existing_pub.summary,
            body=existing_pub.body,
            category=existing_pub.category,
            tags=existing_pub.tags or [],
            created_at=existing_pub.created_at,
            published_at=existing_pub.published_at,
        )

    processed = await process_article(article.extracted_text, title_hint=article.title)

    pub = Publication(
        scraped_article_id=article.id,
        state="draft",
        title=processed.title,
        summary=processed.summary,
        body=processed.body,
        tags=processed.tags,
        category=processed.category,
    )

    db.add(pub)
    await db.flush()

    db.add(
        AIRun(
            scraped_article_id=article.id,
            publication_id=pub.id,
            agent="pipeline",
            status="ok",
            input_text=article.extracted_text[:20000],
            output_text=f"title={processed.title}\nsummary={processed.summary}\ntags={processed.tags}",
        )
    )

    await db.commit()
    await db.refresh(pub)

    return PublicationOut(
        id=pub.id,
        state=pub.state,
        title=pub.title,
        summary=pub.summary,
        body=pub.body,
        category=pub.category,
        tags=pub.tags or [],
        created_at=pub.created_at,
        published_at=pub.published_at,
    )


@router.post("/{publication_id}/publish", response_model=PublicationOut)
async def publish_publication(publication_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> PublicationOut:
    pub = await db.get(Publication, publication_id)
    if not pub:
        raise HTTPException(status_code=404, detail="No existe")

    pub.state = "published"
    pub.published_at = datetime.utcnow()
    await db.commit()
    await db.refresh(pub)

    return PublicationOut(
        id=pub.id,
        state=pub.state,
        title=pub.title,
        summary=pub.summary,
        body=pub.body,
        category=pub.category,
        tags=pub.tags or [],
        created_at=pub.created_at,
        published_at=pub.published_at,
    )


@router.post("/{publication_id}/vote", response_model=VoteTotalsOut)
async def vote_publication(
    publication_id: uuid.UUID,
    payload: VoteRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
) -> VoteTotalsOut:
    pub = await db.get(Publication, publication_id)
    if not pub or pub.state != "published":
        raise HTTPException(status_code=404, detail="No existe")

    voter_key = _voter_key(req)
    vote = await db.scalar(
        select(Vote).where(Vote.publication_id == publication_id, Vote.voter_key == voter_key)
    )
    if vote:
        vote.vote_type = payload.vote_type
    else:
        db.add(Vote(publication_id=publication_id, vote_type=payload.vote_type, voter_key=voter_key))

    await db.commit()

    hot = await db.scalar(
        select(func.count()).select_from(Vote).where(Vote.publication_id == publication_id, Vote.vote_type == "hot")
    )
    cold = await db.scalar(
        select(func.count()).select_from(Vote).where(Vote.publication_id == publication_id, Vote.vote_type == "cold")
    )

    return VoteTotalsOut(publication_id=publication_id, hot=int(hot or 0), cold=int(cold or 0))
