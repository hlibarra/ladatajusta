"""Activate Infobae source"""

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
    """Activate and configure Infobae source"""

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # Update Infobae to make it active and add scraper configuration
        await conn.execute(
            """
            UPDATE scraping_sources
            SET
                is_active = true,
                scraper_script_path = 'infobae/scrape_infobae_db.py',
                sections_to_scrape = ARRAY['politica', 'economia', 'sociedad', 'deportes'],
                max_articles_per_run = 50,
                scraper_config = '{"use_playwright": true, "headless": false}'::jsonb,
                updated_at = NOW()
            WHERE slug = 'infobae'
            """
        )

        # Get updated source
        source = await conn.fetchrow(
            """
            SELECT id, name, base_url, is_active, scraper_script_path, sections_to_scrape
            FROM scraping_sources
            WHERE slug = 'infobae'
            """
        )

        print("=" * 80)
        print("Fuente Infobae activada correctamente")
        print("=" * 80)
        print(f"ID: {source['id']}")
        print(f"Nombre: {source['name']}")
        print(f"URL: {source['base_url']}")
        print(f"Estado: {'ACTIVA' if source['is_active'] else 'INACTIVA'}")
        print(f"Scraper: {source['scraper_script_path']}")
        print(f"Secciones: {', '.join(source['sections_to_scrape'])}")
        print("=" * 80)

        print("\nNOTA: Necesitarás crear el script scraper en:")
        print(f"  scraping/infobae/scrape_infobae_db.py")
        print("\nPuedes usar el scraper de La Gaceta como base.")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
