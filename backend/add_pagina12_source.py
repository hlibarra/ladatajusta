"""
Script to add Página 12 as a scraping source
"""
import asyncio
import asyncpg
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / "scraping" / "pagina12" / ".env"
load_dotenv(dotenv_path=env_path)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "ladatajusta"),
    "user": os.getenv("DB_USER", "ladatajusta"),
    "password": os.getenv("DB_PASSWORD", "ladatajusta"),
}


async def main():
    print("Connecting to database...")
    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # Check if source already exists
        existing = await conn.fetchval(
            "SELECT id FROM scraping_sources WHERE slug = 'pagina12'"
        )

        if existing:
            print(f"Source 'pagina12' already exists with ID: {existing}")
            return

        # Insert new source
        result = await conn.fetchrow(
            """
            INSERT INTO scraping_sources (
                name,
                slug,
                media_type,
                base_url,
                sections_to_scrape,
                max_articles_per_run,
                scraper_script_path,
                is_active,
                scraper_config
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9
            )
            RETURNING id
            """,
            'Página 12',                                    # name
            'pagina12',                                     # slug
            'pagina12',                                     # media_type
            'https://www.pagina12.com.ar',                  # base_url
            ['portada'],                                    # sections_to_scrape
            50,                                             # max_articles_per_run
            'pagina12/scrape_pagina12_db.py',              # scraper_script_path
            True,                                           # is_active
            '{"rss_url": "https://www.pagina12.com.ar/arc/outboundfeeds/rss/portada/"}'  # scraper_config
        )

        print(f"Successfully added Página 12 source with ID: {result['id']}")

    finally:
        await conn.close()
        print("Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
