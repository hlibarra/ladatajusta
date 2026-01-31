"""Check specific publication"""

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
    """Check specific publication"""

    import sys
    if len(sys.argv) > 1:
        pub_id = sys.argv[1]
    else:
        pub_id = "482da316-d8c4-4487-b159-68aac7fb385b"

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # Get publication
        pub = await conn.fetchrow(
            """
            SELECT
                id,
                title,
                slug,
                scraping_item_id,
                content_sin_vueltas,
                content_lo_central,
                content_en_profundidad,
                created_at
            FROM publications
            WHERE id = $1
            """,
            pub_id
        )

        if not pub:
            print(f"No se encontro publicacion con ID: {pub_id}")
            return

        print("=" * 80)
        print(f"PUBLICACION")
        print("=" * 80)
        print(f"ID: {pub['id']}")
        print(f"Titulo: {pub['title']}")
        print(f"Slug: {pub['slug']}")
        print(f"Creada: {pub['created_at']}")
        print(f"Scraping Item ID: {pub['scraping_item_id']}")

        print(f"\nContenidos en publicacion:")
        print(f"  sin_vueltas: {len(pub['content_sin_vueltas']) if pub['content_sin_vueltas'] else 0} caracteres")
        print(f"  lo_central: {len(pub['content_lo_central']) if pub['content_lo_central'] else 0} caracteres")
        print(f"  en_profundidad: {len(pub['content_en_profundidad']) if pub['content_en_profundidad'] else 0} caracteres")

        if not pub['scraping_item_id']:
            print(f"\n[!] Esta publicacion NO esta vinculada a un scraping_item")
            return

        # Get scraping item
        item = await conn.fetchrow(
            """
            SELECT
                id,
                title,
                ai_metadata,
                status
            FROM scraping_items
            WHERE id = $1
            """,
            pub['scraping_item_id']
        )

        if not item:
            print(f"\n[ERROR] No se encontro el scraping_item vinculado")
            return

        print(f"\n" + "=" * 80)
        print(f"SCRAPING ITEM")
        print("=" * 80)
        print(f"ID: {item['id']}")
        print(f"Titulo: {item['title']}")
        print(f"Estado: {item['status']}")

        if not item['ai_metadata']:
            print(f"\n[!] El scraping_item NO tiene ai_metadata")
            return

        metadata = item['ai_metadata']
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        print(f"\nContenidos en scraping_item:")
        sin_vueltas = metadata.get('sin_vueltas')
        lo_central = metadata.get('lo_central')
        en_profundidad = metadata.get('en_profundidad')

        print(f"  sin_vueltas: {len(sin_vueltas) if sin_vueltas else 0} caracteres")
        print(f"  lo_central: {len(lo_central) if lo_central else 0} caracteres")
        print(f"  en_profundidad: {len(en_profundidad) if en_profundidad else 0} caracteres")

        # Check if needs fixing
        has_in_item = sin_vueltas and lo_central and en_profundidad
        has_in_pub = pub['content_sin_vueltas'] and pub['content_lo_central'] and pub['content_en_profundidad']

        if has_in_item and not has_in_pub:
            print(f"\n" + "=" * 80)
            print(f"[!] NECESITA ARREGLO")
            print("=" * 80)
            print(f"El scraping_item TIENE los contenidos pero la publicacion NO")
            print(f"\nPara arreglar, ejecuta:")
            print(f"  python fix_publication.py {pub_id}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
