from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ScrapeRequest, ScrapedArticleOut
from app.db.models import ScrapedArticle
from app.db.session import get_db
from app.scrape.fetch import fetch_and_extract

router = APIRouter()


@router.post("/fetch", response_model=ScrapedArticleOut)
async def fetch_url(payload: ScrapeRequest, db: AsyncSession = Depends(get_db)) -> ScrapedArticleOut:
    # dedupe by URL
    existing = await db.scalar(select(ScrapedArticle).where(ScrapedArticle.source_url == payload.url))
    if existing:
        return ScrapedArticleOut(
            id=existing.id,
            source_name=existing.source_name,
            source_url=existing.source_url,
            title=existing.title,
            extracted_text=existing.extracted_text,
            scraped_at=existing.scraped_at,
        )

    fetched = await fetch_and_extract(payload.url)
    if not fetched.extracted_text:
        raise HTTPException(status_code=422, detail="No se pudo extraer texto")

    # dedupe by content hash (mismo texto aunque cambie la URL)
    existing_by_hash = await db.scalar(select(ScrapedArticle).where(ScrapedArticle.text_hash == fetched.text_hash))
    if existing_by_hash:
        return ScrapedArticleOut(
            id=existing_by_hash.id,
            source_name=existing_by_hash.source_name,
            source_url=existing_by_hash.source_url,
            title=existing_by_hash.title,
            extracted_text=existing_by_hash.extracted_text,
            scraped_at=existing_by_hash.scraped_at,
        )

    article = ScrapedArticle(
        source_name=payload.source_name,
        source_url=payload.url,
        title=fetched.title,
        raw_html=fetched.raw_html,
        extracted_text=fetched.extracted_text,
        published_at=fetched.published_at,
        text_hash=fetched.text_hash,
    )

    db.add(article)
    await db.commit()
    await db.refresh(article)

    return ScrapedArticleOut(
        id=article.id,
        source_name=article.source_name,
        source_url=article.source_url,
        title=article.title,
        extracted_text=article.extracted_text,
        scraped_at=article.scraped_at,
    )
