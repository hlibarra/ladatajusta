"""Check publication content"""

import asyncio
import asyncpg
import os
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
    """Check publication by slug"""

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # Get publication by slug
        slug = "estudiantes-logra-una-epica-victoria-sobre-rivadavia-en-el-ultimo-segundo"

        row = await conn.fetchrow(
            """
            SELECT
                id,
                title,
                content_sin_vueltas,
                content_lo_central,
                content_en_profundidad,
                scraping_item_id
            FROM publications
            WHERE slug = $1
            """,
            slug
        )

        if not row:
            print(f"No se encontró publicación con slug: {slug}")
            return

        print("=" * 80)
        print(f"Publicación: {row['title']}")
        print("=" * 80)
        print(f"ID: {row['id']}")
        print(f"Scraping Item ID: {row['scraping_item_id']}")
        print(f"\nContenidos:")
        print(f"  Sin vueltas: {'SI' if row['content_sin_vueltas'] else 'NO'}")
        print(f"  Lo central: {'SI' if row['content_lo_central'] else 'NO'}")
        print(f"  En profundidad: {'SI' if row['content_en_profundidad'] else 'NO'}")

        if row['scraping_item_id']:
            print(f"\n" + "=" * 80)
            print(f"Verificando Scraping Item...")
            print("=" * 80)

            item = await conn.fetchrow(
                """
                SELECT
                    id,
                    title,
                    ai_metadata
                FROM scraping_items
                WHERE id = $1
                """,
                row['scraping_item_id']
            )

            if item:
                print(f"Scraping Item encontrado: {item['title']}")
                if item['ai_metadata']:
                    metadata = dict(item['ai_metadata'])
                    print(f"\nAI Metadata:")
                    print(f"  sin_vueltas: {'SI' if metadata.get('sin_vueltas') else 'NO'}")
                    print(f"  lo_central: {'SI' if metadata.get('lo_central') else 'NO'}")
                    print(f"  en_profundidad: {'SI' if metadata.get('en_profundidad') else 'NO'}")

                    if metadata.get('sin_vueltas'):
                        print(f"\n--- Sin vueltas ({len(metadata.get('sin_vueltas', ''))} caracteres) ---")
                        print(metadata.get('sin_vueltas'))
                else:
                    print("  NO tiene ai_metadata")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
