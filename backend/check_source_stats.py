"""Check scraping source statistics"""

import asyncio
import asyncpg
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

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
    """Check all scraping sources statistics"""

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        rows = await conn.fetch(
            """
            SELECT
                name,
                slug,
                is_active,
                last_scraped_at,
                last_scrape_status,
                last_scrape_items_count,
                total_items_scraped,
                total_scrape_runs,
                consecutive_errors
            FROM scraping_sources
            ORDER BY name
            """
        )

        print("=" * 100)
        print("SCRAPING SOURCES STATISTICS")
        print("=" * 100)

        for row in rows:
            print(f"\nSource: {row['name']} ({row['slug']})")
            print(f"  Active: {row['is_active']}")
            print(f"  Last Scraped: {row['last_scraped_at']}")
            print(f"  Last Status: {row['last_scrape_status']}")
            print(f"  Last Items Count: {row['last_scrape_items_count']}")
            print(f"  Total Items Scraped: {row['total_items_scraped']}")
            print(f"  Total Scrape Runs: {row['total_scrape_runs']}")
            print(f"  Consecutive Errors: {row['consecutive_errors']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
