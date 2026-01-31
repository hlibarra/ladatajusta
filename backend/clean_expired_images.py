"""Limpiar URLs de imágenes expiradas de DALL-E"""

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
    """Limpiar URLs expiradas"""

    print("=" * 80)
    print("LIMPIANDO URLs DE IMAGENES EXPIRADAS")
    print("=" * 80)

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # Limpiar publications
        result = await conn.execute("""
            UPDATE publications
            SET media = '[]'::jsonb
            WHERE media::text LIKE '%oaidalleapiprodscus.blob.core.windows.net%'
        """)

        pubs_cleaned = int(result.split()[-1]) if result else 0
        print(f"\nPublicaciones limpiadas: {pubs_cleaned}")

        # Limpiar scraping_items (excepto los no publicados, para poder regenerar)
        result = await conn.execute("""
            UPDATE scraping_items
            SET image_urls = NULL
            WHERE image_urls IS NOT NULL
            AND array_to_string(image_urls, ',') LIKE '%oaidalleapiprodscus.blob.core.windows.net%'
            AND status = 'published'
        """)

        items_cleaned = int(result.split()[-1]) if result else 0
        print(f"Scraping items publicados limpiados: {items_cleaned}")

        print("\n" + "=" * 80)
        print("LISTO!")
        print("=" * 80)
        print("\nAhora puedes:")
        print("1. Ir a los scraping items que NO están publicados")
        print("2. Generar imágenes nuevas con el botón 'Generar Imagen'")
        print("3. Las nuevas imágenes serán permanentes y no expirarán")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
