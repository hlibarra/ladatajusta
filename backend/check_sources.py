"""Check existing scraping sources"""

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
    """Check existing sources"""

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # Check if table exists
        table_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'scraping_sources');"
        )

        if not table_exists:
            print("La tabla scraping_sources NO existe")
            return

        print("La tabla scraping_sources existe\n")

        # Get all sources
        sources = await conn.fetch(
            """
            SELECT id, name, base_url, is_active, last_scraped_at, total_items_scraped
            FROM scraping_sources
            ORDER BY name
            """
        )

        if not sources:
            print("No hay fuentes en la base de datos")
        else:
            print(f"Fuentes encontradas: {len(sources)}\n")
            print("=" * 100)
            for source in sources:
                status = "ACTIVA" if source['is_active'] else "INACTIVA"
                scraped = source['total_items_scraped'] or 0
                last = source['last_scraped_at'].strftime("%Y-%m-%d %H:%M") if source['last_scraped_at'] else "Nunca"

                print(f"Nombre: {source['name']}")
                print(f"URL: {source['base_url']}")
                print(f"Estado: {status}")
                print(f"Última scrapeada: {last}")
                print(f"Total artículos: {scraped}")
                print(f"ID: {source['id']}")
                print("=" * 100)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
