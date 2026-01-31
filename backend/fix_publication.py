"""Fix publication by copying content from scraping_item"""

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
    """Fix publication by copying content from scraping_item"""

    import sys

    # Get publication ID from command line or use default
    if len(sys.argv) > 1:
        publication_id = sys.argv[1]
    else:
        publication_id = "86e2cda2-4ce2-4574-b666-5488729cc695"

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # Get publication

        pub = await conn.fetchrow(
            """
            SELECT
                id,
                title,
                scraping_item_id,
                content_sin_vueltas,
                content_lo_central,
                content_en_profundidad
            FROM publications
            WHERE id = $1
            """,
            publication_id
        )

        if not pub:
            print(f"No se encontro publicacion con ID: {publication_id}")
            return

        print("=" * 80)
        print(f"Publicacion: {pub['title']}")
        print("=" * 80)

        if not pub['scraping_item_id']:
            print("ERROR: La publicacion no tiene scraping_item_id vinculado")
            return

        # Get scraping item
        item = await conn.fetchrow(
            """
            SELECT
                id,
                title,
                ai_metadata
            FROM scraping_items
            WHERE id = $1
            """,
            pub['scraping_item_id']
        )

        if not item:
            print("ERROR: No se encontro el scraping_item")
            return

        print(f"\nScraping Item: {item['title']}")

        if not item['ai_metadata']:
            print("ERROR: El scraping_item no tiene ai_metadata")
            return

        # Extract content from ai_metadata
        metadata = item['ai_metadata']

        # If metadata is a string, parse it as JSON
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        sin_vueltas = metadata.get('sin_vueltas')
        lo_central = metadata.get('lo_central')
        en_profundidad = metadata.get('en_profundidad')

        print(f"\nContenidos en scraping_item:")
        print(f"  sin_vueltas: {len(sin_vueltas) if sin_vueltas else 0} caracteres")
        print(f"  lo_central: {len(lo_central) if lo_central else 0} caracteres")
        print(f"  en_profundidad: {len(en_profundidad) if en_profundidad else 0} caracteres")

        if not (sin_vueltas and lo_central and en_profundidad):
            print("\nERROR: El scraping_item no tiene todos los contenidos")
            return

        # Update publication
        print(f"\nActualizando publicacion...")

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
            publication_id
        )

        print(f"\n[OK] Publicacion actualizada exitosamente!")
        print(f"\nVerifica en: http://localhost:4321/p/estudiantes-logra-una-epica-victoria-sobre-rivadavia-en-el-ultimo-segundo")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
