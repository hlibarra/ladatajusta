"""
Script para listar publicaciones con multimedia.
Ejecutar: python -m scripts.list_publications_with_media
"""
import asyncio
import sys
from pathlib import Path

# Fix for Windows event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.models import Publication
from app.db.session import AsyncSessionLocal
from sqlalchemy import select


async def list_publications():
    async with AsyncSessionLocal() as db:
        # Get all published publications
        result = await db.execute(
            select(Publication)
            .where(Publication.state == "published")
            .order_by(Publication.created_at.desc())
            .limit(15)
        )
        publications = result.scalars().all()

        print("Ultimas 15 publicaciones:\n")
        for i, pub in enumerate(publications, 1):
            has_media = pub.media and len(pub.media) > 0
            media_count = len(pub.media) if has_media else 0
            status = f"CON {media_count} media" if has_media else "SIN media"
            print(f"{i}. [{status}] {pub.title[:60]}")
            print(f"   ID: {pub.id}")
            print(f"   URL: http://localhost:4321/p/{pub.id}\n")


if __name__ == "__main__":
    asyncio.run(list_publications())
