"""
Script para verificar el campo media en una publicación.
Ejecutar: python -m scripts.check_media
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
import json


async def check_media():
    async with AsyncSessionLocal() as db:
        # Get the publication
        pub_id = "7864a34d-bde1-4e9a-9feb-daf70fd595f1"
        pub = await db.get(Publication, pub_id)

        if not pub:
            print(f"Publication {pub_id} not found")
            return

        print(f"Title: {pub.title}")
        print(f"Media field type: {type(pub.media)}")
        print(f"Media content: {pub.media}")
        print(f"\nMedia as JSON:")
        print(json.dumps(pub.media, indent=2))


if __name__ == "__main__":
    asyncio.run(check_media())
