"""
Script para verificar los niveles de lectura en la base de datos.
Ejecutar: python -m scripts.check_reading_levels
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


async def check_reading_levels():
    async with AsyncSessionLocal() as db:
        # Get first publication
        pub = (await db.execute(select(Publication).limit(1))).scalar_one_or_none()

        if not pub:
            print("No hay publicaciones en la base de datos.")
            return

        print(f"Título: {pub.title}\n")
        print(f"Sin vueltas ({len(pub.content_sin_vueltas or '')} chars):")
        print(f"  {pub.content_sin_vueltas}\n")
        print(f"Lo central ({len(pub.content_lo_central or '')} chars):")
        print(f"  {pub.content_lo_central}\n")
        print(f"En profundidad ({len(pub.content_en_profundidad or '')} chars):")
        print(f"  {pub.content_en_profundidad[:200]}...\n")


if __name__ == "__main__":
    asyncio.run(check_reading_levels())
