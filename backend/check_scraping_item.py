"""Check scraping item and its publication"""

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
    """Check scraping item and its publication"""

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # Get scraping item
        item_id = "8ca95de8-60ed-437e-bdda-0fe4aacaa9bc"

        item = await conn.fetchrow(
            """
            SELECT
                id,
                title,
                publication_id,
                status,
                ai_metadata
            FROM scraping_items
            WHERE id = $1
            """,
            item_id
        )

        if not item:
            print(f"No se encontro scraping_item con ID: {item_id}")
            return

        print("=" * 80)
        print(f"Scraping Item: {item['title']}")
        print("=" * 80)
        print(f"Estado: {item['status']}")
        print(f"Publication ID: {item['publication_id']}")

        # Check if has ai_metadata
        if item['ai_metadata']:
            metadata = item['ai_metadata']
            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            print(f"\nContenidos en scraping_item:")
            print(f"  sin_vueltas: {len(metadata.get('sin_vueltas', '')) if metadata.get('sin_vueltas') else 0} caracteres")
            print(f"  lo_central: {len(metadata.get('lo_central', '')) if metadata.get('lo_central') else 0} caracteres")
            print(f"  en_profundidad: {len(metadata.get('en_profundidad', '')) if metadata.get('en_profundidad') else 0} caracteres")
        else:
            print("\nNO tiene ai_metadata")

        # If published, check publication
        if item['publication_id']:
            print(f"\n" + "=" * 80)
            print(f"Verificando Publicacion...")
            print("=" * 80)

            pub = await conn.fetchrow(
                """
                SELECT
                    id,
                    title,
                    slug,
                    content_sin_vueltas,
                    content_lo_central,
                    content_en_profundidad
                FROM publications
                WHERE id = $1
                """,
                item['publication_id']
            )

            if pub:
                print(f"Titulo: {pub['title']}")
                print(f"Slug: {pub['slug']}")
                print(f"\nContenidos en publicacion:")
                print(f"  sin_vueltas: {len(pub['content_sin_vueltas']) if pub['content_sin_vueltas'] else 0} caracteres")
                print(f"  lo_central: {len(pub['content_lo_central']) if pub['content_lo_central'] else 0} caracteres")
                print(f"  en_profundidad: {len(pub['content_en_profundidad']) if pub['content_en_profundidad'] else 0} caracteres")

                print(f"\nURL: http://localhost:4321/p/{pub['slug']}")

                # If publication is missing content but scraping_item has it, offer to fix
                if item['ai_metadata']:
                    metadata = item['ai_metadata']
                    if isinstance(metadata, str):
                        metadata = json.loads(metadata)

                    has_content_in_item = (
                        metadata.get('sin_vueltas') and
                        metadata.get('lo_central') and
                        metadata.get('en_profundidad')
                    )
                    has_content_in_pub = (
                        pub['content_sin_vueltas'] and
                        pub['content_lo_central'] and
                        pub['content_en_profundidad']
                    )

                    if has_content_in_item and not has_content_in_pub:
                        print(f"\n[!] La publicacion NO tiene contenidos pero el scraping_item SI")
                        print(f"    Se puede arreglar copiando los contenidos")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
