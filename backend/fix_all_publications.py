"""Fix all publications by copying content from their scraping_items"""

import asyncio
import asyncpg
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / "scraping" / "lagaceta" / ".env"
load_dotenv(dotenv_path=env_path)

# Database connection
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "ladatajusta"),
    "user": os.getenv("DB_USER", "ladatajusta"),
    "password": os.getenv("DB_PASSWORD", "ladatajusta"),
}


async def main():
    """Fix all publications that are missing content"""

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        print("=" * 80)
        print("ARREGLANDO PUBLICACIONES SIN CONTENIDOS")
        print("=" * 80)

        # Find all publications linked to scraping_items that are missing content
        rows = await conn.fetch(
            """
            SELECT
                p.id as pub_id,
                p.title as pub_title,
                p.slug,
                p.content_sin_vueltas,
                p.content_lo_central,
                p.content_en_profundidad,
                si.id as item_id,
                si.title as item_title,
                si.ai_metadata
            FROM publications p
            INNER JOIN scraping_items si ON p.scraping_item_id = si.id
            WHERE p.scraping_item_id IS NOT NULL
              AND (
                  p.content_sin_vueltas IS NULL OR
                  p.content_lo_central IS NULL OR
                  p.content_en_profundidad IS NULL
              )
            """
        )

        if not rows:
            print("\nNo se encontraron publicaciones para arreglar")
            return

        print(f"\nSe encontraron {len(rows)} publicaciones sin contenidos\n")

        fixed_count = 0
        skipped_count = 0

        for row in rows:
            pub_id = row['pub_id']
            pub_title = row['pub_title']
            slug = row['slug']
            ai_metadata = row['ai_metadata']

            print(f"\n[{fixed_count + skipped_count + 1}/{len(rows)}] {pub_title}")

            if not ai_metadata:
                print(f"  SALTANDO: No tiene ai_metadata")
                skipped_count += 1
                continue

            # Parse metadata
            metadata = ai_metadata
            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            sin_vueltas = metadata.get('sin_vueltas')
            lo_central = metadata.get('lo_central')
            en_profundidad = metadata.get('en_profundidad')

            if not (sin_vueltas and lo_central and en_profundidad):
                print(f"  SALTANDO: ai_metadata incompleto")
                skipped_count += 1
                continue

            # Update publication
            await conn.execute(
                """
                UPDATE publications
                SET
                    content_sin_vueltas = $1,
                    content_lo_central = $2,
                    content_en_profundidad = $3
                WHERE id = $4
                """,
                sin_vueltas,
                lo_central,
                en_profundidad,
                pub_id
            )

            print(f"  ARREGLADO: {len(sin_vueltas)}, {len(lo_central)}, {len(en_profundidad)} chars")
            print(f"  URL: http://localhost:4321/p/{slug}")
            fixed_count += 1

        print(f"\n" + "=" * 80)
        print(f"RESUMEN")
        print("=" * 80)
        print(f"Total encontradas: {len(rows)}")
        print(f"Arregladas: {fixed_count}")
        print(f"Saltadas: {skipped_count}")
        print("=" * 80)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
