"""
Script para agregar slugs a las publicaciones existentes.
Ejecutar: python -m scripts.add_slugs
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
from app.db.models import Publication
from app.core.slugify import slugify, generate_unique_slug
from sqlalchemy import text, select


async def add_slugs():
    async with AsyncSessionLocal() as db:
        print("Agregando campo 'slug' a la tabla publications...")

        # Check if column already exists
        check_query = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='publications' AND column_name='slug';
        """)
        result = await db.execute(check_query)
        exists = result.fetchone()

        if not exists:
            # Add slug column
            alter_query = text("""
                ALTER TABLE publications
                ADD COLUMN slug VARCHAR(512);
            """)
            await db.execute(alter_query)
            await db.commit()
            print("[OK] Campo 'slug' agregado a la tabla publications")

        # Generate slugs for existing publications
        print("\nGenerando slugs para publicaciones existentes...")

        publications = (await db.scalars(select(Publication))).all()
        existing_slugs = set()

        for pub in publications:
            if pub.slug:
                existing_slugs.add(pub.slug)
                continue

            base_slug = slugify(pub.title)
            unique_slug = generate_unique_slug(base_slug, existing_slugs)

            pub.slug = unique_slug
            existing_slugs.add(unique_slug)

            print(f"  {pub.title[:60]}... -> {unique_slug}")

        await db.commit()

        # Add unique constraint and index
        try:
            constraint_query = text("""
                ALTER TABLE publications
                ADD CONSTRAINT publications_slug_key UNIQUE (slug);
            """)
            await db.execute(constraint_query)

            index_query = text("""
                CREATE INDEX IF NOT EXISTS ix_publications_slug ON publications(slug);
            """)
            await db.execute(index_query)

            await db.commit()
            print("\n[OK] Constraint e index agregados")
        except Exception as e:
            print(f"\n[NOTA] Constraint/index ya existe o error: {e}")

        print(f"\n[OK] Se generaron slugs para {len(publications)} publicaciones!")


if __name__ == "__main__":
    asyncio.run(add_slugs())
