"""
Script para listar publicaciones con niveles de lectura.
Ejecutar: python -m scripts.list_publications_with_levels
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
            .limit(10)
        )
        publications = result.scalars().all()

        print("Últimas 10 publicaciones:\n")
        for i, pub in enumerate(publications, 1):
            has_levels = pub.content_sin_vueltas and pub.content_lo_central and pub.content_en_profundidad
            status = "✓ CON niveles" if has_levels else "✗ SIN niveles"
            print(f"{i}. [{status}] {pub.title[:60]}")
            print(f"   ID: {pub.id}")
            print(f"   URL: http://localhost:4321/p/{pub.id}\n")


if __name__ == "__main__":
    asyncio.run(list_publications())
