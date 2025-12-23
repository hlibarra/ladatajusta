"""
Script para agregar campo de multimedia a la tabla publications.
Ejecutar: python -m scripts.add_media_field
"""
import asyncio
import sys
from pathlib import Path

# Fix for Windows event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import AsyncSessionLocal
from sqlalchemy import text


async def add_media_field():
    async with AsyncSessionLocal() as db:
        print("Agregando campo 'media' a la tabla publications...")

        # Check if column already exists
        check_query = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='publications' AND column_name='media';
        """)
        result = await db.execute(check_query)
        exists = result.fetchone()

        if exists:
            print("[OK] El campo 'media' ya existe en la tabla publications.")
            return

        # Add media column as JSONB
        alter_query = text("""
            ALTER TABLE publications
            ADD COLUMN media JSONB DEFAULT '[]'::jsonb;
        """)

        await db.execute(alter_query)
        await db.commit()

        print("[OK] Campo 'media' agregado exitosamente a la tabla publications!")
        print("  Tipo: JSONB")
        print("  Default: []")
        print("  Formato: [{\"type\": \"image|video\", \"url\": \"...\", \"caption\": \"...\", \"order\": 0}, ...]")


if __name__ == "__main__":
    asyncio.run(add_media_field())
