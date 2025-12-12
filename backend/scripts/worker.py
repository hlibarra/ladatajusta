from __future__ import annotations

import asyncio
import os

from sqlalchemy import select

from app.ai.pipeline import process_article
from app.db.models import Publication, ScrapedArticle
from app.db.session import AsyncSessionLocal


POLL_SECONDS = float(os.getenv("WORKER_POLL_SECONDS", "5"))


async def run_once() -> int:
    async with AsyncSessionLocal() as db:
        article = await db.scalar(
            select(ScrapedArticle)
            .where(~ScrapedArticle.id.in_(select(Publication.scraped_article_id)))
            .order_by(ScrapedArticle.scraped_at.asc())
            .limit(1)
        )
        if not article:
            return 0

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
        await db.commit()
        return 1


async def main() -> None:
    while True:
        n = await run_once()
        await asyncio.sleep(POLL_SECONDS if n == 0 else 0.2)


if __name__ == "__main__":
    asyncio.run(main())
