"""
Scraper Service - Automated Scraping Pipeline
Runs continuously, executing the full scraping pipeline at intervals:
1. Scrape from active sources
2. Prepare items for AI processing
3. Process items with AI

Configuration via environment variables:
- SCRAPE_INTERVAL_MINUTES: Minutes between scraping runs (default: 60)
- AI_PROCESS_INTERVAL_MINUTES: Minutes between AI processing (default: 30)
- PREPARE_HOURS_AGO: Hours of items to prepare for AI (default: 24)
- CONTROL_SERVER_PORT: Port for control API (default: 8080)
"""

import asyncio
import asyncpg
import os
import sys
import signal
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / "lagaceta" / ".env"
load_dotenv(dotenv_path=env_path)

# Reconfigure stdout for Docker logs
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Configuration
SCRAPE_INTERVAL_MINUTES = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "60"))
AI_PROCESS_INTERVAL_MINUTES = int(os.getenv("AI_PROCESS_INTERVAL_MINUTES", "30"))
PREPARE_HOURS_AGO = int(os.getenv("PREPARE_HOURS_AGO", "24"))
CONTROL_SERVER_PORT = int(os.getenv("CONTROL_SERVER_PORT", "8080"))

# Database connection
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "ladatajusta"),
    "user": os.getenv("DB_USER", "ladatajusta"),
    "password": os.getenv("DB_PASSWORD", "ladatajusta"),
}

# Import control server
from control_server import controller, start_control_server

# Graceful shutdown flag
shutdown_requested = False


def signal_handler(signum, frame):
    global shutdown_requested
    log(f"Received signal {signum}, requesting graceful shutdown...", "SIGNAL")
    shutdown_requested = True
    controller.stop_requested = True


# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def log(message: str, level: str = "INFO"):
    """Log with timestamp - outputs to console and control server"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)
    # Also send to control server for streaming
    controller.add_log(message, level)


async def get_db_connection():
    """Get database connection with retry"""
    max_retries = 5
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            conn = await asyncpg.connect(**DB_CONFIG)
            return conn
        except Exception as e:
            if attempt < max_retries - 1:
                log(f"Database connection failed (attempt {attempt + 1}/{max_retries}): {e}", "WARN")
                await asyncio.sleep(retry_delay)
            else:
                log(f"Failed to connect to database after {max_retries} attempts", "ERROR")
                raise


async def get_active_sources(conn, source_ids: list = None):
    """Get active scraping sources, optionally filtered by IDs

    - source_ids=None: returns all active sources
    - source_ids=[]: returns empty list (no sources)
    - source_ids=[id1, id2]: returns only those sources
    """
    if source_ids is not None:
        if len(source_ids) == 0:
            return []  # Explicitly no sources selected
        rows = await conn.fetch(
            """
            SELECT
                id, name, slug, media_type, base_url,
                sections_to_scrape, max_articles_per_run,
                scraper_script_path, scraper_config
            FROM scraping_sources
            WHERE id = ANY($1::uuid[])
            ORDER BY name
            """,
            source_ids
        )
    else:
        rows = await conn.fetch(
            """
            SELECT
                id, name, slug, media_type, base_url,
                sections_to_scrape, max_articles_per_run,
                scraper_script_path, scraper_config
            FROM scraping_sources
            WHERE is_active = true
            ORDER BY name
            """
        )
    return [dict(row) for row in rows]


async def update_source_stats(conn, source_id, status: str, message: str, items_count: int = 0):
    """Update scraping source statistics"""
    if status == 'success':
        await conn.execute(
            """
            UPDATE scraping_sources
            SET last_scraped_at = NOW(),
                last_scrape_status = $1,
                last_scrape_message = $2,
                last_scrape_items_count = $3,
                total_items_scraped = total_items_scraped + $3,
                total_scrape_runs = total_scrape_runs + 1,
                consecutive_errors = 0,
                updated_at = NOW()
            WHERE id = $4
            """,
            status, message, items_count, source_id
        )
    else:
        await conn.execute(
            """
            UPDATE scraping_sources
            SET last_scraped_at = NOW(),
                last_scrape_status = $1,
                last_scrape_message = $2,
                last_scrape_items_count = $3,
                total_scrape_runs = total_scrape_runs + 1,
                consecutive_errors = consecutive_errors + 1,
                updated_at = NOW()
            WHERE id = $4
            """,
            status, message, items_count, source_id
        )

    # Auto-disable if too many errors
    await conn.execute(
        """
        UPDATE scraping_sources
        SET is_active = false,
            last_scrape_message = 'Auto-disabled: ' || last_scrape_message
        WHERE id = $1 AND consecutive_errors >= max_consecutive_errors
        """,
        source_id
    )


async def run_scraper_for_source(conn, source: dict):
    """Execute scraper for a specific source"""
    source_id = source['id']
    source_name = source['name']
    scraper_path = source.get('scraper_script_path')

    log(f"Scraping: {source_name}")
    controller.current_task = f"Scraping: {source_name}"
    controller.current_source = source_name

    if not scraper_path:
        await update_source_stats(conn, source_id, "error", "No scraper path configured", 0)
        return 0

    scraper_file = Path(__file__).parent / scraper_path
    if not scraper_file.exists():
        await update_source_stats(conn, source_id, "error", f"Scraper not found: {scraper_path}", 0)
        return 0

    try:
        spec = importlib.util.spec_from_file_location(f"scraper_{source['slug']}", scraper_file)
        if not spec or not spec.loader:
            raise Exception("Could not load scraper module")

        scraper_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scraper_module)

        if not hasattr(scraper_module, 'main'):
            raise Exception("Scraper has no main() function")

        result = await scraper_module.main()

        if isinstance(result, dict):
            items_count = result.get('items_scraped', 0)
            status = result.get('status', 'success')
            message = result.get('message', f'Scraped {items_count} items')
        else:
            items_count = 0
            status = 'success'
            message = 'Scraper completed'

        log(f"  {source_name}: {message}")
        await update_source_stats(conn, source_id, status, message, items_count)
        return items_count

    except Exception as e:
        error_msg = str(e)[:500]
        log(f"  {source_name}: Error - {error_msg}", "ERROR")
        await update_source_stats(conn, source_id, "error", error_msg, 0)
        return 0


async def run_scraping(source_ids: list = None):
    """Run scraping for active sources, optionally filtered by IDs"""
    log("=" * 50)
    if source_ids:
        log(f"Starting scraping for {len(source_ids)} selected source(s)")
    else:
        log("Starting scraping cycle (all active sources)")
    controller.current_task = "Scraping"

    total_items = 0
    conn = await get_db_connection()
    try:
        sources = await get_active_sources(conn, source_ids)

        if not sources:
            log("No sources found")
            return 0

        log(f"Found {len(sources)} source(s)")

        for source in sources:
            if shutdown_requested or controller.stop_requested:
                log("Shutdown requested, stopping scraping")
                break
            items = await run_scraper_for_source(conn, source)
            total_items += items

        log(f"Scraping cycle completed. Total items: {total_items}")
        controller.items_processed["scraped"] += total_items
        return total_items

    finally:
        await conn.close()
        controller.current_task = None
        controller.current_source = None


async def prepare_for_ai():
    """Mark scraped items as ready for AI processing"""
    log("Preparing items for AI processing")
    controller.current_task = "Preparing for AI"

    conn = await get_db_connection()
    try:
        result = await conn.execute(
            """
            UPDATE scraping_items
            SET status = 'ready_for_ai',
                status_message = 'Auto-prepared for AI',
                status_updated_at = NOW()
            WHERE status = 'scraped'
              AND scraped_at >= NOW() - INTERVAL '1 hour' * $1
            """,
            PREPARE_HOURS_AGO
        )

        count = int(result.split()[-1]) if result else 0
        log(f"  Marked {count} items as ready for AI")
        return count

    finally:
        await conn.close()
        controller.current_task = None


async def process_ai():
    """Process items with AI"""
    log("Starting AI processing")
    controller.current_task = "AI Processing"

    # Import and run process_ai module
    process_ai_file = Path(__file__).parent / "lagaceta" / "process_ai.py"

    if not process_ai_file.exists():
        log("process_ai.py not found, skipping AI processing", "WARN")
        controller.current_task = None
        return

    try:
        spec = importlib.util.spec_from_file_location("process_ai", process_ai_file)
        if spec and spec.loader:
            process_ai_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(process_ai_module)

            if hasattr(process_ai_module, 'main'):
                result = await process_ai_module.main()
                if isinstance(result, dict):
                    controller.items_processed["ai_processed"] += result.get("processed", 0)
                log("AI processing completed")
            else:
                log("process_ai.py has no main() function", "WARN")

    except Exception as e:
        log(f"AI processing error: {e}", "ERROR")
    finally:
        controller.current_task = None


async def auto_prepare():
    """Auto-prepare items for publishing after quality and duplicate checks"""
    log("Starting auto-prepare")
    controller.current_task = "Auto-Prepare"

    # Import and run auto_prepare module
    auto_prepare_file = Path(__file__).parent / "auto_prepare.py"

    if not auto_prepare_file.exists():
        log("auto_prepare.py not found, skipping auto-prepare", "WARN")
        controller.current_task = None
        return

    try:
        spec = importlib.util.spec_from_file_location("auto_prepare", auto_prepare_file)
        if spec and spec.loader:
            auto_prepare_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(auto_prepare_module)

            if hasattr(auto_prepare_module, 'main'):
                stats = await auto_prepare_module.main()
                if stats:
                    controller.items_processed["prepared"] += stats.get("ready", 0)
                    log(f"Auto-prepare: {stats.get('ready', 0)} listos, {stats.get('duplicates', 0)} duplicados, {stats.get('quality_failed', 0)} calidad insuficiente")
            else:
                log("auto_prepare.py has no main() function", "WARN")

    except Exception as e:
        log(f"Auto-prepare error: {e}", "ERROR")
    finally:
        controller.current_task = None


def update_next_times(last_scrape: datetime, last_ai: datetime):
    """Update next scheduled times in controller"""
    scrape_interval = controller.config["scrape_interval_minutes"]
    ai_interval = controller.config["ai_process_interval_minutes"]

    controller.next_scrape_time = last_scrape + timedelta(minutes=scrape_interval)
    controller.next_ai_time = last_ai + timedelta(minutes=ai_interval)


async def main():
    """Main service loop"""
    global shutdown_requested

    # Start control server
    log("Starting control server...")
    runner = await start_control_server(port=CONTROL_SERVER_PORT)

    # Initialize controller config from env
    controller.config["scrape_interval_minutes"] = SCRAPE_INTERVAL_MINUTES
    controller.config["ai_process_interval_minutes"] = AI_PROCESS_INTERVAL_MINUTES
    controller.config["prepare_hours_ago"] = PREPARE_HOURS_AGO

    log("=" * 60)
    log("SCRAPER SERVICE STARTED")
    log("=" * 60)
    log(f"Control API: http://0.0.0.0:{CONTROL_SERVER_PORT}")
    log(f"Scrape interval: {SCRAPE_INTERVAL_MINUTES} minutes")
    log(f"AI process interval: {AI_PROCESS_INTERVAL_MINUTES} minutes")
    log(f"Prepare hours ago: {PREPARE_HOURS_AGO} hours")
    log(f"Database host: {DB_CONFIG['host']}")

    controller.status = "running"

    # Wait for database to be ready
    log("Waiting for database...")
    await asyncio.sleep(10)

    last_scrape = datetime.min
    last_ai_process = datetime.min

    while not shutdown_requested and not controller.stop_requested:
        now = datetime.now()

        # Get current intervals from controller (can be changed via API)
        scrape_interval = controller.config["scrape_interval_minutes"]
        ai_interval = controller.config["ai_process_interval_minutes"]

        # Check for run-now request
        if controller.run_now_requested:
            controller.run_now_requested = False
            source_ids = controller.run_source_ids
            controller.run_source_ids = None  # Reset after use
            log("Running immediate scraping cycle...")
            try:
                await run_scraping(source_ids)
                await prepare_for_ai()
                await process_ai()
                await auto_prepare()
                last_scrape = datetime.now()
                last_ai_process = datetime.now()
                controller.last_scrape_time = last_scrape
                controller.last_ai_time = last_ai_process
            except Exception as e:
                log(f"Immediate run error: {e}", "ERROR")
            continue

        # Check for restart request
        if controller.restart_requested:
            controller.restart_requested = False
            log("Restarting service loop...")
            last_scrape = datetime.min
            last_ai_process = datetime.min
            continue

        # Check for process-ai request (AI processing + auto-prepare)
        if controller.process_ai_requested:
            controller.process_ai_requested = False
            log("Running AI processing (manual trigger)...")
            try:
                await process_ai()
                await auto_prepare()  # Auto-prepare after AI processing
                last_ai_process = datetime.now()
                controller.last_ai_time = last_ai_process
            except Exception as e:
                log(f"AI processing error: {e}", "ERROR")
            continue

        # Check for auto-prepare request
        if controller.auto_prepare_requested:
            controller.auto_prepare_requested = False
            log("Running auto-prepare (manual trigger)...")
            try:
                await auto_prepare()
            except Exception as e:
                log(f"Auto-prepare error: {e}", "ERROR")
            continue

        # Check if it's time to scrape
        minutes_since_scrape = (now - last_scrape).total_seconds() / 60
        if minutes_since_scrape >= scrape_interval:
            try:
                # Use selected sources from config (None = all active)
                config_source_ids = controller.config.get("selected_source_ids")
                await run_scraping(config_source_ids)
                await prepare_for_ai()
                last_scrape = datetime.now()
                controller.last_scrape_time = last_scrape
            except Exception as e:
                log(f"Scraping cycle error: {e}", "ERROR")

        # Check if it's time to process AI
        minutes_since_ai = (now - last_ai_process).total_seconds() / 60
        if minutes_since_ai >= ai_interval:
            try:
                await process_ai()
                # Auto-prepare after AI processing
                await auto_prepare()
                last_ai_process = datetime.now()
                controller.last_ai_time = last_ai_process
            except Exception as e:
                log(f"AI processing error: {e}", "ERROR")

        # Update next scheduled times
        update_next_times(last_scrape, last_ai_process)

        # Sleep for 1 minute between checks
        if not shutdown_requested and not controller.stop_requested:
            log(f"Next check in 1 minute...")
            await asyncio.sleep(60)

    controller.status = "stopped"
    log("Service shutdown complete")

    # Cleanup
    await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
