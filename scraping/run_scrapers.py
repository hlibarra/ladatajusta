"""
Orchestrator for running all active scrapers
Reads configuration from scraping_sources table and executes scrapers
"""

import asyncio
import asyncpg
import os
import sys
import importlib.util
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / "lagaceta" / ".env"
load_dotenv(dotenv_path=env_path)

# Reconfigure stdout for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Database connection
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "ladatajusta"),
    "user": os.getenv("DB_USER", "ladatajusta"),
    "password": os.getenv("DB_PASSWORD", "ladatajusta"),
}


async def get_active_sources(conn):
    """Get all active scraping sources from database"""

    rows = await conn.fetch(
        """
        SELECT
            id,
            name,
            slug,
            media_type,
            base_url,
            sections_to_scrape,
            max_articles_per_run,
            scraper_script_path,
            scraper_config
        FROM scraping_sources
        WHERE is_active = true
        ORDER BY name
        """
    )

    return [dict(row) for row in rows]


async def update_source_stats(
    conn,
    source_id,  # UUID type from database
    status: str,
    message: str,
    items_count: int = 0
):
    """Update scraping source statistics after a run"""

    # Calculate consecutive_errors value based on status
    consecutive_errors_value = 0 if status == 'success' else None

    if consecutive_errors_value == 0:
        # Success: reset consecutive_errors to 0
        await conn.execute(
            """
            UPDATE scraping_sources
            SET
                last_scraped_at = NOW(),
                last_scrape_status = $1,
                last_scrape_message = $2,
                last_scrape_items_count = $3,
                total_items_scraped = total_items_scraped + $3,
                total_scrape_runs = total_scrape_runs + 1,
                consecutive_errors = 0,
                updated_at = NOW()
            WHERE id = $4
            """,
            status,
            message,
            items_count,
            source_id
        )
    else:
        # Error: increment consecutive_errors
        await conn.execute(
            """
            UPDATE scraping_sources
            SET
                last_scraped_at = NOW(),
                last_scrape_status = $1,
                last_scrape_message = $2,
                last_scrape_items_count = $3,
                total_items_scraped = total_items_scraped + $3,
                total_scrape_runs = total_scrape_runs + 1,
                consecutive_errors = consecutive_errors + 1,
                updated_at = NOW()
            WHERE id = $4
            """,
            status,
            message,
            items_count,
            source_id
        )

    # Auto-disable if too many consecutive errors
    await conn.execute(
        """
        UPDATE scraping_sources
        SET
            is_active = false,
            last_scrape_message = 'Auto-disabled due to consecutive errors: ' || last_scrape_message
        WHERE id = $1
          AND consecutive_errors >= max_consecutive_errors
        """,
        source_id
    )


async def run_scraper_for_source(conn, source: dict):
    """Execute scraper for a specific source"""

    source_id = source['id']  # Keep as UUID, don't convert to string
    source_name = source['name']
    scraper_path = source.get('scraper_script_path')

    print(f"\n{'=' * 70}")
    print(f"[START] Scraping: {source_name}")
    print(f"{'=' * 70}")
    print(f"Source ID: {source_id}")
    print(f"Media Type: {source['media_type']}")
    print(f"Base URL: {source['base_url']}")
    print(f"Sections: {', '.join(source['sections_to_scrape'] or [])}")
    print(f"Max Articles: {source['max_articles_per_run']}")

    if not scraper_path:
        error_msg = f"No scraper script path configured for {source_name}"
        print(f"[ERROR] {error_msg}")
        await update_source_stats(conn, source_id, "error", error_msg, 0)
        return

    # Check if scraper file exists
    scraper_file = Path(__file__).parent / scraper_path
    if not scraper_file.exists():
        error_msg = f"Scraper file not found: {scraper_path}"
        print(f"[ERROR] {error_msg}")
        await update_source_stats(conn, source_id, "error", error_msg, 0)
        return

    try:
        # Import and run the scraper module
        spec = importlib.util.spec_from_file_location(f"scraper_{source['slug']}", scraper_file)
        if not spec or not spec.loader:
            raise Exception("Could not load scraper module")

        scraper_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scraper_module)

        # Check if module has main() function
        if not hasattr(scraper_module, 'main'):
            raise Exception("Scraper module does not have a main() function")

        # Run the scraper
        print(f"[RUN] Executing scraper...")
        result = await scraper_module.main()

        # Process result
        if isinstance(result, dict):
            items_count = result.get('items_scraped', 0)
            status = result.get('status', 'success')
            message = result.get('message', f'Scraped {items_count} items')
        else:
            items_count = 0
            status = 'success'
            message = 'Scraper completed'

        print(f"[OK] {message}")
        await update_source_stats(conn, source_id, status, message, items_count)

    except Exception as e:
        error_msg = f"Error running scraper: {str(e)}"
        print(f"[ERROR] {error_msg}")
        await update_source_stats(conn, source_id, "error", error_msg, 0)


async def main():
    """Main orchestrator function"""

    print("=" * 70)
    print("[START] Scraping Orchestrator - La Data Justa")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Connect to database
    print("\n[DB] Connecting to PostgreSQL...")
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        print("[DB] Connected successfully")
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        return

    try:
        # Get active sources
        print("\n[FETCH] Getting active scraping sources...")
        sources = await get_active_sources(conn)

        if not sources:
            print("[INFO] No active scraping sources found")
            return

        print(f"[FETCH] Found {len(sources)} active source(s):")
        for source in sources:
            print(f"  - {source['name']} ({source['media_type']})")

        # Run scrapers sequentially
        total_items = 0
        successful = 0
        failed = 0

        for source in sources:
            try:
                await run_scraper_for_source(conn, source)
                successful += 1
            except Exception as e:
                print(f"[ERROR] Failed to run scraper for {source['name']}: {e}")
                failed += 1

        # Summary
        print("\n" + "=" * 70)
        print("[DONE] Scraping orchestrator completed")
        print("=" * 70)
        print(f"Total sources: {len(sources)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    finally:
        await conn.close()
        print("\n[DB] Connection closed")


if __name__ == "__main__":
    asyncio.run(main())
