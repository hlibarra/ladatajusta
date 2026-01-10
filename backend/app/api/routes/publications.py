from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.pipeline import process_article
from app.api.deps import CurrentAdmin
from app.api.schemas import (
    AgentOut,
    MediaItem,
    PaginatedPublications,
    PublicationOut,
    PublicationUpdate,
    StateChange,
    VoteRequest,
    VoteTotalsOut,
)
from app.db.models import Agent, AIRun, Publication, ScrapedArticle, Vote
from app.db.session import get_db

router = APIRouter()


def _to_publication_out(pub: Publication) -> PublicationOut:
    """Convert Publication model to PublicationOut schema"""
    agent_out = None
    if pub.agent:
        agent_out = AgentOut(
            id=pub.agent.id,
            name=pub.agent.name,
            slug=pub.agent.slug,
            description=pub.agent.description,
            specialization=pub.agent.specialization,
            avatar_url=pub.agent.avatar_url,
        )

    # Extract first image URL from media array
    image_url = None
    if pub.media:
        for item in pub.media:
            if isinstance(item, dict) and item.get("type") == "image" and item.get("url"):
                image_url = item["url"]
                break

    return PublicationOut(
        id=pub.id,
        state=pub.state,
        title=pub.title,
        slug=pub.slug,
        summary=pub.summary,
        body=pub.body,
        category=pub.category,
        tags=pub.tags or [],
        created_at=pub.created_at,
        published_at=pub.published_at,
        agent=agent_out,
        content_sin_vueltas=pub.content_sin_vueltas,
        content_lo_central=pub.content_lo_central,
        content_en_profundidad=pub.content_en_profundidad,
        media=pub.media or [],
        image_url=image_url,
    )


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
        .options(selectinload(Publication.agent))
        .where(Publication.state == state)
        .order_by(Publication.published_at.desc().nullslast(), Publication.created_at.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    rows = (await db.scalars(q)).all()
    return [_to_publication_out(r) for r in rows]


@router.get("/search", response_model=PaginatedPublications)
async def search_publications(
    db: AsyncSession = Depends(get_db),
    q: Annotated[str | None, Query(description="Texto a buscar")] = None,
    category: Annotated[str | None, Query(description="Filtrar por categoria")] = None,
    tags: Annotated[list[str] | None, Query(description="Filtrar por tags")] = None,
    from_date: Annotated[date | None, Query(description="Desde fecha")] = None,
    to_date: Annotated[date | None, Query(description="Hasta fecha")] = None,
    state: Annotated[str, Query(description="Estado")] = "published",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedPublications:
    conditions = [Publication.state == state]

    if q:
        search_term = f"%{q}%"
        conditions.append(
            or_(
                Publication.title.ilike(search_term),
                Publication.summary.ilike(search_term),
                Publication.body.ilike(search_term),
            )
        )

    if category:
        conditions.append(Publication.category == category)

    if tags:
        conditions.append(Publication.tags.overlap(tags))

    if from_date:
        conditions.append(Publication.published_at >= datetime.combine(from_date, datetime.min.time()))

    if to_date:
        conditions.append(Publication.published_at <= datetime.combine(to_date, datetime.max.time()))

    # Count total
    count_q = select(func.count()).select_from(Publication).where(and_(*conditions))
    total = await db.scalar(count_q) or 0

    # Fetch items
    items_q = (
        select(Publication)
        .options(selectinload(Publication.agent))
        .where(and_(*conditions))
        .order_by(Publication.published_at.desc().nullslast(), Publication.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.scalars(items_q)).all()

    items = [_to_publication_out(r) for r in rows]

    return PaginatedPublications(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(items)) < total,
    )


@router.get("/{publication_id_or_slug}", response_model=PublicationOut)
async def get_publication(publication_id_or_slug: str, db: AsyncSession = Depends(get_db)) -> PublicationOut:
    # Try to parse as UUID first
    try:
        pub_id = uuid.UUID(publication_id_or_slug)
        q = select(Publication).options(selectinload(Publication.agent)).where(Publication.id == pub_id)
    except ValueError:
        # If not a UUID, treat as slug
        q = select(Publication).options(selectinload(Publication.agent)).where(Publication.slug == publication_id_or_slug)

    pub = await db.scalar(q)
    if not pub:
        raise HTTPException(status_code=404, detail="No existe")
    return _to_publication_out(pub)


@router.post("/process/{scraped_id}", response_model=PublicationOut)
async def process_scraped(scraped_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> PublicationOut:
    article = await db.get(ScrapedArticle, scraped_id)
    if not article:
        raise HTTPException(status_code=404, detail="ScrapedArticle no existe")

    # if already processed
    existing_pub = await db.scalar(
        select(Publication)
        .options(selectinload(Publication.agent))
        .where(Publication.scraped_article_id == scraped_id)
    )
    if existing_pub:
        return _to_publication_out(existing_pub)

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

    # Reload with agent relationship
    q = select(Publication).options(selectinload(Publication.agent)).where(Publication.id == pub.id)
    pub = await db.scalar(q)

    return _to_publication_out(pub)


@router.post("/{publication_id}/publish", response_model=PublicationOut)
async def publish_publication(publication_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> PublicationOut:
    q = select(Publication).options(selectinload(Publication.agent)).where(Publication.id == publication_id)
    pub = await db.scalar(q)
    if not pub:
        raise HTTPException(status_code=404, detail="No existe")

    pub.state = "published"
    pub.published_at = datetime.utcnow()
    await db.commit()
    await db.refresh(pub)

    return _to_publication_out(pub)


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


@router.put("/{publication_id}", response_model=PublicationOut)
async def update_publication(
    publication_id: uuid.UUID,
    payload: PublicationUpdate,
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> PublicationOut:
    q = select(Publication).options(selectinload(Publication.agent)).where(Publication.id == publication_id)
    pub = await db.scalar(q)
    if not pub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No existe")

    if payload.title is not None:
        pub.title = payload.title
    if payload.summary is not None:
        pub.summary = payload.summary
    if payload.body is not None:
        pub.body = payload.body
    if payload.category is not None:
        pub.category = payload.category
    if payload.tags is not None:
        pub.tags = payload.tags
    if payload.content_sin_vueltas is not None:
        pub.content_sin_vueltas = payload.content_sin_vueltas
    if payload.content_lo_central is not None:
        pub.content_lo_central = payload.content_lo_central
    if payload.content_en_profundidad is not None:
        pub.content_en_profundidad = payload.content_en_profundidad
    if payload.media is not None:
        pub.media = [item.model_dump() for item in payload.media]

    await db.commit()
    await db.refresh(pub)

    return _to_publication_out(pub)


@router.delete("/{publication_id}")
async def delete_publication(
    publication_id: uuid.UUID,
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> Response:
    pub = await db.get(Publication, publication_id)
    if not pub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No existe")

    await db.delete(pub)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{publication_id}/state", response_model=PublicationOut)
async def change_state(
    publication_id: uuid.UUID,
    payload: StateChange,
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> PublicationOut:
    q = select(Publication).options(selectinload(Publication.agent)).where(Publication.id == publication_id)
    pub = await db.scalar(q)
    if not pub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No existe")

    pub.state = payload.state
    if payload.state == "published" and pub.published_at is None:
        pub.published_at = datetime.utcnow()

    await db.commit()
    await db.refresh(pub)

    return _to_publication_out(pub)


@router.post("/{publication_id}/restore", response_model=PublicationOut)
async def restore_publication(
    publication_id: uuid.UUID,
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> PublicationOut:
    q = select(Publication).options(selectinload(Publication.agent)).where(Publication.id == publication_id)
    pub = await db.scalar(q)
    if not pub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No existe")

    if pub.state != "discarded":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden restaurar publicaciones descartadas",
        )

    pub.state = "draft"
    await db.commit()
    await db.refresh(pub)

    return _to_publication_out(pub)
