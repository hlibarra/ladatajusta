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
import uuid
import json
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
# In Docker: uses env vars from docker-compose
# Locally: searches for .env in parent directories
load_dotenv()

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

# Import Telegram notifier
from telegram_notifier import get_notifier

# Initialize Telegram notifier
telegram_notifier = get_notifier()

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
    result = await conn.execute(
        """
        UPDATE scraping_sources
        SET is_active = false,
            last_scrape_message = 'Auto-disabled: ' || last_scrape_message
        WHERE id = $1 AND consecutive_errors >= max_consecutive_errors
        RETURNING name, consecutive_errors
        """,
        source_id
    )

    # Notify if source was auto-disabled
    if result != "UPDATE 0":
        disabled_source = await conn.fetchrow(
            "SELECT name, consecutive_errors FROM scraping_sources WHERE id = $1 AND is_active = false",
            source_id
        )
        if disabled_source and telegram_notifier:
            try:
                await telegram_notifier.notify_source_disabled(
                    source_name=disabled_source['name'],
                    error_count=disabled_source['consecutive_errors']
                )
            except Exception as e:
                log(f"Telegram notification failed: {e}", "WARN")


async def run_scraper_for_source(conn, source: dict, scraping_run_id: str = None):
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

        # Pass scraping_run_id to the scraper if it supports it
        import inspect
        sig = inspect.signature(scraper_module.main)
        if 'scraping_run_id' in sig.parameters:
            result = await scraper_module.main(scraping_run_id=scraping_run_id)
        else:
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

        # Notify source error
        if telegram_notifier:
            try:
                consecutive = await conn.fetchval(
                    "SELECT consecutive_errors FROM scraping_sources WHERE id = $1",
                    source_id
                )
                await telegram_notifier.notify_source_error(
                    source_name=source_name,
                    error_message=error_msg,
                    consecutive_errors=consecutive or 0
                )
            except Exception as notify_err:
                log(f"Telegram notification failed: {notify_err}", "WARN")

        return 0


async def run_scraping(source_ids: list = None, triggered_by_user_id: str = None):
    """Run scraping for active sources, optionally filtered by IDs"""
    start_time = datetime.now()
    log("=" * 50)
    if source_ids:
        log(f"Starting scraping for {len(source_ids)} selected source(s)")
    else:
        log("Starting scraping cycle (all active sources)")
    controller.current_task = "Scraping"

    total_items = 0
    total_failed = 0
    total_duplicate = 0
    errors_list = []
    scraping_run_id = None

    conn = await get_db_connection()
    try:
        sources = await get_active_sources(conn, source_ids)

        if not sources:
            log("No sources found")
            return 0

        log(f"Found {len(sources)} source(s)")

        # Create scraping run record
        try:
            triggered_by = "manual" if source_ids else "automatic"
            sources_processed_ids = [str(s['id']) for s in sources]

            # Generate UUID explicitly in Python to avoid database DEFAULT issues
            scraping_run_id = uuid.uuid4()

            await conn.execute(
                """
                INSERT INTO scraping_runs (
                    id,
                    started_at,
                    status,
                    triggered_by,
                    triggered_by_user_id,
                    sources_processed,
                    items_scraped,
                    items_failed,
                    items_duplicate
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                scraping_run_id,
                start_time,
                'running',
                triggered_by,
                triggered_by_user_id,
                sources_processed_ids,
                0,  # items_scraped (will be updated at end)
                0,  # items_failed (will be updated at end)
                0   # items_duplicate (will be updated at end)
            )
            log(f"Created scraping run: {scraping_run_id}")
        except Exception as e:
            log(f"Failed to create scraping run record: {e}", "WARN")

        # Notify scraping start
        if telegram_notifier:
            try:
                mode = "manual" if source_ids else "automático"
                source_names = [s['name'] for s in sources]

                # Get user email if triggered by user
                user_email = None
                if triggered_by_user_id:
                    try:
                        user_uuid = uuid.UUID(triggered_by_user_id) if isinstance(triggered_by_user_id, str) else triggered_by_user_id
                        user_row = await conn.fetchrow(
                            "SELECT email FROM users WHERE id = $1",
                            user_uuid
                        )
                        if user_row:
                            user_email = user_row['email']
                    except Exception:
                        pass  # Ignore if user not found

                await telegram_notifier.notify_scrape_start(
                    source_count=len(sources),
                    mode=mode,
                    source_names=source_names,
                    user_email=user_email
                )
            except Exception as e:
                log(f"Telegram notification failed: {e}", "WARN")

        for source in sources:
            if shutdown_requested or controller.stop_requested:
                log("Shutdown requested, stopping scraping")
                break
            try:
                items = await run_scraper_for_source(conn, source, scraping_run_id)
                total_items += items
            except Exception as e:
                total_failed += 1
                error_detail = {
                    "source": source['name'],
                    "error": str(e)[:500],
                    "timestamp": datetime.now().isoformat()
                }
                errors_list.append(error_detail)

        log(f"Scraping cycle completed. Total items: {total_items}")
        controller.items_processed["scraped"] += total_items

        # Update scraping run with final results
        if scraping_run_id:
            try:
                finish_time = datetime.now()
                duration = int((finish_time - start_time).total_seconds())
                final_status = 'cancelled' if (shutdown_requested or controller.stop_requested) else 'completed'

                await conn.execute(
                    """
                    UPDATE scraping_runs
                    SET finished_at = $1,
                        duration_seconds = $2,
                        status = $3,
                        items_scraped = $4,
                        items_failed = $5,
                        items_duplicate = $6,
                        errors = $7::jsonb
                    WHERE id = $8
                    """,
                    finish_time,
                    duration,
                    final_status,
                    total_items,
                    total_failed,
                    total_duplicate,
                    json.dumps(errors_list),
                    scraping_run_id
                )
                log(f"Updated scraping run {scraping_run_id}: {final_status}")
            except Exception as e:
                log(f"Failed to update scraping run: {e}", "WARN")

        # Notify scraping complete
        if telegram_notifier:
            try:
                duration = (datetime.now() - start_time).total_seconds()
                await telegram_notifier.notify_scrape_complete(
                    total_items=total_items,
                    sources_processed=len(sources),
                    duration_seconds=duration
                )
            except Exception as e:
                log(f"Telegram notification failed: {e}", "WARN")

        return total_items

    except Exception as e:
        # Mark run as failed
        if scraping_run_id:
            try:
                finish_time = datetime.now()
                duration = int((finish_time - start_time).total_seconds())
                await conn.execute(
                    """
                    UPDATE scraping_runs
                    SET finished_at = $1,
                        duration_seconds = $2,
                        status = 'failed',
                        error_message = $3
                    WHERE id = $4
                    """,
                    finish_time,
                    duration,
                    str(e)[:500],
                    scraping_run_id
                )
            except Exception as update_error:
                log(f"Failed to update scraping run on error: {update_error}", "WARN")
        raise

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


async def process_ai(mode: str = "automático"):
    """Process items with AI"""
    start_time = datetime.now()
    log("Starting AI processing")
    controller.current_task = "AI Processing"

    # Import and run process_ai module
    process_ai_file = Path(__file__).parent / "lagaceta" / "process_ai.py"

    if not process_ai_file.exists():
        log("process_ai.py not found, skipping AI processing", "WARN")
        controller.current_task = None
        return

    try:
        # Get pending items count for notification
        pending_count = 0
        try:
            conn = await get_db_connection()
            pending_count = await conn.fetchval(
                "SELECT COUNT(*) FROM scraping_items WHERE status IN ('scraped', 'ready_for_ai') AND retry_count < max_retries"
            )
            await conn.close()
        except Exception:
            pass

        # Notify AI processing start
        if telegram_notifier and pending_count > 0:
            try:
                await telegram_notifier.notify_ai_start(
                    pending_count=pending_count,
                    mode=mode
                )
            except Exception as e:
                log(f"Telegram notification failed: {e}", "WARN")

        spec = importlib.util.spec_from_file_location("process_ai", process_ai_file)
        if spec and spec.loader:
            process_ai_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(process_ai_module)

            if hasattr(process_ai_module, 'main'):
                result = await process_ai_module.main()
                processed_count = 0
                failed_count = 0
                if isinstance(result, dict):
                    processed_count = result.get("processed", 0)
                    failed_count = result.get("failed", 0)
                    controller.items_processed["ai_processed"] += processed_count
                log("AI processing completed")

                # Notify AI processing complete
                if telegram_notifier:
                    try:
                        duration = (datetime.now() - start_time).total_seconds()
                        await telegram_notifier.notify_ai_complete(
                            processed=processed_count,
                            failed=failed_count,
                            duration_seconds=duration
                        )
                    except Exception as e:
                        log(f"Telegram notification failed: {e}", "WARN")
            else:
                log("process_ai.py has no main() function", "WARN")

    except Exception as e:
        log(f"AI processing error: {e}", "ERROR")
        # Notify error
        if telegram_notifier:
            try:
                await telegram_notifier.notify_error(
                    task_name="AI Processing",
                    error_message=str(e)
                )
            except Exception as notify_err:
                log(f"Telegram notification failed: {notify_err}", "WARN")
    finally:
        controller.current_task = None


async def auto_prepare(mode: str = "automático"):
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
        # Get pending items count for notification
        pending_count = 0
        try:
            conn = await get_db_connection()
            pending_count = await conn.fetchval(
                "SELECT COUNT(*) FROM scraping_items WHERE status = 'ai_completed'"
            )
            await conn.close()
        except Exception:
            pass

        # Notify auto-prepare start
        if telegram_notifier and pending_count > 0:
            try:
                await telegram_notifier.notify_auto_prepare_start(
                    pending_count=pending_count,
                    mode=mode
                )
            except Exception as e:
                log(f"Telegram notification failed: {e}", "WARN")

        spec = importlib.util.spec_from_file_location("auto_prepare", auto_prepare_file)
        if spec and spec.loader:
            auto_prepare_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(auto_prepare_module)

            if hasattr(auto_prepare_module, 'main'):
                stats = await auto_prepare_module.main()
                if stats:
                    controller.items_processed["prepared"] += stats.get("ready", 0)
                    log(f"Auto-prepare: {stats.get('ready', 0)} listos, {stats.get('duplicates', 0)} duplicados, {stats.get('quality_failed', 0)} calidad insuficiente")

                    # Notify auto-prepare complete
                    if telegram_notifier:
                        try:
                            await telegram_notifier.notify_auto_prepare(
                                ready=stats.get("ready", 0),
                                duplicates=stats.get("duplicates", 0),
                                quality_failed=stats.get("quality_failed", 0)
                            )
                        except Exception as e:
                            log(f"Telegram notification failed: {e}", "WARN")
            else:
                log("auto_prepare.py has no main() function", "WARN")

    except Exception as e:
        log(f"Auto-prepare error: {e}", "ERROR")
        # Notify error
        if telegram_notifier:
            try:
                await telegram_notifier.notify_error(
                    task_name="Auto-Prepare",
                    error_message=str(e)
                )
            except Exception as notify_err:
                log(f"Telegram notification failed: {notify_err}", "WARN")
    finally:
        controller.current_task = None


async def auto_publish(mode: str = "automático"):
    """Auto-publish items from sources with auto_publish enabled after delay period"""
    log("Starting auto-publish")
    controller.current_task = "Auto-Publish"

    # Import and run auto_publish module
    auto_publish_file = Path(__file__).parent / "auto_publish.py"

    if not auto_publish_file.exists():
        log("auto_publish.py not found, skipping auto-publish", "WARN")
        controller.current_task = None
        return

    try:
        # Get pending items count for notification
        pending_count = 0
        try:
            conn = await get_db_connection()
            pending_count = await conn.fetchval(
                "SELECT COUNT(*) FROM scraping_items WHERE status = 'ready_to_publish'"
            )
            await conn.close()
        except Exception:
            pass

        # Notify auto-publish start
        if telegram_notifier and pending_count > 0:
            try:
                await telegram_notifier.notify_auto_publish_start(
                    pending_count=pending_count,
                    mode=mode
                )
            except Exception as e:
                log(f"Telegram notification failed: {e}", "WARN")

        spec = importlib.util.spec_from_file_location("auto_publish", auto_publish_file)
        if spec and spec.loader:
            auto_publish_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(auto_publish_module)

            if hasattr(auto_publish_module, 'main'):
                stats = await auto_publish_module.main()
                if stats:
                    published = stats.get("published", 0)
                    if published > 0:
                        controller.items_processed["auto_published"] = controller.items_processed.get("auto_published", 0) + published
                        log(f"Auto-publish: {published} publicados automáticamente")

                    # Notify auto-publish complete (even if 0 published)
                    if telegram_notifier:
                        try:
                            await telegram_notifier.notify_auto_publish(published=published)
                        except Exception as e:
                            log(f"Telegram notification failed: {e}", "WARN")
            else:
                log("auto_publish.py has no main() function", "WARN")

    except Exception as e:
        log(f"Auto-publish error: {e}", "ERROR")
        # Notify error
        if telegram_notifier:
            try:
                await telegram_notifier.notify_error(
                    task_name="Auto-Publish",
                    error_message=str(e)
                )
            except Exception as notify_err:
                log(f"Telegram notification failed: {notify_err}", "WARN")
    finally:
        controller.current_task = None


async def curate_news(dry_run: bool = False):
    """Curate and publish news using intelligent selection algorithm"""
    mode = "simulación" if dry_run else "publicación"
    log(f"Starting news curation ({mode})")
    controller.current_task = "Curación de noticias"

    # Import and run news_curator module
    curator_file = Path(__file__).parent / "news_curator.py"

    if not curator_file.exists():
        log("news_curator.py not found, skipping curation", "WARN")
        controller.current_task = None
        return None

    try:
        import asyncpg
        # Create pool for curator
        pool = await asyncpg.create_pool(**DB_CONFIG)

        try:
            spec = importlib.util.spec_from_file_location("news_curator", curator_file)
            if spec and spec.loader:
                curator_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(curator_module)

                if hasattr(curator_module, 'curate_and_publish'):
                    # Get config from controller
                    target_count = controller.config.get("curator_target_count", 12)
                    max_per_category = controller.config.get("curator_max_per_category", 3)
                    max_per_source = controller.config.get("curator_max_per_source", 3)

                    stats = await curator_module.curate_and_publish(
                        pool,
                        target_count=target_count,
                        max_per_category=max_per_category,
                        max_per_source=max_per_source,
                        dry_run=dry_run,
                        log_func=log
                    )

                    if stats:
                        if not dry_run and stats.get("published_count", 0) > 0:
                            controller.items_processed["curated"] += stats.get("published_count", 0)
                        log(f"Curation complete: {stats.get('total_available', 0)} disponibles, {stats.get('selected_count', 0)} seleccionados, {stats.get('published_count', 0)} publicados")

                        # Notify curator complete
                        if telegram_notifier and not dry_run:
                            try:
                                await telegram_notifier.notify_curator_complete(
                                    published=stats.get("published_count", 0),
                                    available=stats.get("total_available", 0),
                                    selected=stats.get("selected_count", 0)
                                )
                            except Exception as e:
                                log(f"Telegram notification failed: {e}", "WARN")

                        return stats
                else:
                    log("news_curator.py has no curate_and_publish() function", "WARN")
        finally:
            await pool.close()

    except Exception as e:
        import traceback
        log(f"Curation error: {type(e).__name__}: {e}", "ERROR")
        log(f"Curation traceback: {traceback.format_exc()}", "ERROR")
        # Notify error
        if telegram_notifier:
            try:
                await telegram_notifier.notify_error(
                    task_name="News Curation",
                    error_message=str(e)
                )
            except Exception as notify_err:
                log(f"Telegram notification failed: {notify_err}", "WARN")
    finally:
        controller.current_task = None

    return None


def update_next_times(last_scrape: datetime, last_ai: datetime, last_curate: datetime = None):
    """Update next scheduled times in controller"""
    scrape_interval = controller.config["scrape_interval_minutes"]
    ai_interval = controller.config["ai_process_interval_minutes"]
    curator_interval = controller.config.get("curator_interval_minutes", 120)
    curator_enabled = controller.config.get("curator_enabled", False)

    controller.next_scrape_time = last_scrape + timedelta(minutes=scrape_interval)
    controller.next_ai_time = last_ai + timedelta(minutes=ai_interval)

    if curator_enabled and last_curate:
        controller.next_curate_time = last_curate + timedelta(minutes=curator_interval)
    else:
        controller.next_curate_time = None


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

    # Send Telegram notification for service start
    if telegram_notifier:
        try:
            await telegram_notifier.start()
            await telegram_notifier.notify_service_start(
                scrape_interval=controller.config.get("scrape_interval_minutes", SCRAPE_INTERVAL_MINUTES),
                ai_interval=controller.config.get("ai_process_interval_minutes", AI_PROCESS_INTERVAL_MINUTES),
                control_url=f"http://0.0.0.0:{CONTROL_SERVER_PORT}",
                scrape_enabled=controller.config.get("scrape_enabled", True),
                ai_enabled=controller.config.get("ai_process_enabled", True),
                auto_prepare_enabled=controller.config.get("auto_prepare_enabled", True),
                auto_publish_enabled=controller.config.get("auto_publish_enabled", True)
            )
        except Exception as e:
            log(f"Telegram notification failed: {e}", "WARN")

    # Wait for database to be ready
    log("Waiting for database...")
    await asyncio.sleep(10)

    last_scrape = datetime.min
    last_ai_process = datetime.min
    last_curate = datetime.min

    while not shutdown_requested and not controller.stop_requested:
        now = datetime.now()

        # Get current intervals from controller (can be changed via API)
        scrape_interval = controller.config["scrape_interval_minutes"]
        ai_interval = controller.config["ai_process_interval_minutes"]

        # Check for run-now request (scraping only, no AI processing)
        if controller.run_now_requested:
            controller.run_now_requested = False
            source_ids = controller.run_source_ids
            user_id = controller.run_user_id
            controller.run_source_ids = None  # Reset after use
            controller.run_user_id = None
            log("Running immediate scraping (scraping only)...")
            try:
                await run_scraping(source_ids, triggered_by_user_id=user_id)
                last_scrape = datetime.now()
                controller.last_scrape_time = last_scrape
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

        # Check for process-ai request (AI processing only)
        if controller.process_ai_requested:
            controller.process_ai_requested = False
            log("Running AI processing (manual trigger)...")
            try:
                await prepare_for_ai()  # Mark scraped items as ready_for_ai
                await process_ai(mode="manual")  # Process with AI
                last_ai_process = datetime.now()
                controller.last_ai_time = last_ai_process
            except Exception as e:
                log(f"AI processing error: {e}", "ERROR")
            continue

        # Check for auto-prepare request (validation only)
        if controller.auto_prepare_requested:
            controller.auto_prepare_requested = False
            log("Running auto-prepare (manual trigger)...")
            try:
                await auto_prepare(mode="manual")
            except Exception as e:
                log(f"Auto-prepare error: {e}", "ERROR")
            continue

        # Check for auto-publish request
        if controller.auto_publish_requested:
            controller.auto_publish_requested = False
            log("Running auto-publish (manual trigger)...")
            try:
                await auto_publish(mode="manual")
            except Exception as e:
                log(f"Auto-publish error: {e}", "ERROR")
            continue

        # Check for curator request
        if controller.curate_now_requested:
            controller.curate_now_requested = False
            dry_run = controller.curate_dry_run
            controller.curate_dry_run = False
            log(f"Running news curation (manual trigger, dry_run={dry_run})...")
            try:
                await curate_news(dry_run=dry_run)
                if not dry_run:
                    last_curate = datetime.now()
                    controller.last_curate_time = last_curate
            except Exception as e:
                log(f"Curation error: {e}", "ERROR")
            continue

        # Check if it's time to scrape (only if enabled)
        scrape_enabled = controller.config.get("scrape_enabled", True)
        if scrape_enabled:
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

        # Check if it's time to process AI (only if enabled)
        ai_enabled = controller.config.get("ai_process_enabled", True)
        if ai_enabled:
            minutes_since_ai = (now - last_ai_process).total_seconds() / 60
            if minutes_since_ai >= ai_interval:
                try:
                    await process_ai()
                    # Auto-prepare after AI processing (only if enabled)
                    auto_prepare_enabled = controller.config.get("auto_prepare_enabled", True)
                    if auto_prepare_enabled:
                        await auto_prepare()
                    # Auto-publish after auto-prepare (only if enabled)
                    auto_publish_enabled = controller.config.get("auto_publish_enabled", True)
                    if auto_publish_enabled:
                        await auto_publish()
                    last_ai_process = datetime.now()
                    controller.last_ai_time = last_ai_process
                except Exception as e:
                    log(f"AI processing error: {e}", "ERROR")

        # Check if it's time to run curator (if enabled)
        curator_enabled = controller.config.get("curator_enabled", False)
        curator_interval = controller.config.get("curator_interval_minutes", 120)
        if curator_enabled:
            minutes_since_curate = (now - last_curate).total_seconds() / 60
            if minutes_since_curate >= curator_interval:
                try:
                    await curate_news(dry_run=False)
                    last_curate = datetime.now()
                    controller.last_curate_time = last_curate
                except Exception as e:
                    log(f"Scheduled curation error: {e}", "ERROR")

        # Update next scheduled times
        update_next_times(last_scrape, last_ai_process, last_curate)

        # Sleep for 1 minute between checks
        if not shutdown_requested and not controller.stop_requested:
            log(f"Next check in 1 minute...")
            await asyncio.sleep(60)

    controller.status = "stopped"
    log("Service shutdown complete")

    # Send Telegram notification for service stop
    if telegram_notifier:
        try:
            uptime_seconds = int((datetime.now() - controller.start_time).total_seconds())
            await telegram_notifier.notify_service_stop(
                uptime_seconds=uptime_seconds,
                items_scraped=controller.items_processed.get("scraped", 0),
                items_ai_processed=controller.items_processed.get("ai_processed", 0)
            )
            await telegram_notifier.stop()
        except Exception as e:
            log(f"Telegram notification failed: {e}", "WARN")

    # Cleanup
    await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
