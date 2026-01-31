"""
Prepare Scraped Items for AI Processing
Marks scraped items as ready for AI processing
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Reconfigure stdout for Windows unicode support
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


async def show_stats(conn):
    """Show statistics of items by status"""
    print("\n" + "=" * 60)
    print("STATISTICS - SCRAPING ITEMS")
    print("=" * 60)

    # Count by status
    rows = await conn.fetch(
        """
        SELECT status, COUNT(*) as count
        FROM scraping_items
        WHERE source_media = 'lagaceta'
        GROUP BY status
        ORDER BY count DESC
        """
    )

    print("\nItems by status:")
    for row in rows:
        print(f"  {row['status']:20} → {row['count']:5} items")

    # Total
    total = await conn.fetchval(
        "SELECT COUNT(*) FROM scraping_items WHERE source_media = 'lagaceta'"
    )
    print(f"\nTotal items: {total}")


async def mark_ready_for_ai(conn, hours_ago: int = 24):
    """Mark recent scraped items as ready for AI processing"""

    print(f"\nMarking items from last {hours_ago} hours as 'ready_for_ai'...")

    result = await conn.execute(
        """
        UPDATE scraping_items
        SET status = 'ready_for_ai',
            status_message = 'Prepared for AI processing',
            status_updated_at = NOW()
        WHERE source_media = 'lagaceta'
          AND status = 'scraped'
          AND scraped_at >= NOW() - INTERVAL '1 hour' * $1
        """,
        hours_ago
    )

    # Extract count from result
    count = int(result.split()[-1]) if result else 0
    print(f"[OK] {count} items marked as ready for AI")

    return count


async def mark_all_scraped(conn):
    """Mark ALL scraped items as ready for AI"""

    print("\nMarking ALL scraped items as 'ready_for_ai'...")

    result = await conn.execute(
        """
        UPDATE scraping_items
        SET status = 'ready_for_ai',
            status_message = 'Prepared for AI processing',
            status_updated_at = NOW()
        WHERE source_media = 'lagaceta'
          AND status = 'scraped'
        """
    )

    count = int(result.split()[-1]) if result else 0
    print(f"[OK] {count} items marked as ready for AI")

    return count


async def reset_failed_items(conn):
    """Reset items that failed AI processing"""

    print("\nResetting items with AI processing errors...")

    result = await conn.execute(
        """
        UPDATE scraping_items
        SET status = 'ready_for_ai',
            retry_count = 0,
            last_error = NULL,
            last_error_at = NULL,
            status_message = 'Reset for AI retry',
            status_updated_at = NOW()
        WHERE source_media = 'lagaceta'
          AND status = 'error'
          AND last_error LIKE '%AI%'
        """
    )

    count = int(result.split()[-1]) if result else 0
    print(f"[OK] {count} items reset")

    return count


async def main():
    """Main interactive menu"""

    print("=" * 60)
    print("PREPARE ITEMS FOR AI PROCESSING")
    print("=" * 60)

    # Connect to database
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        print("[OK] Connected to PostgreSQL\n")
    except Exception as e:
        print(f"[ERROR] Failed to connect: {e}")
        return

    try:
        # Show current stats
        await show_stats(conn)

        # Interactive menu
        print("\n" + "=" * 60)
        print("OPTIONS")
        print("=" * 60)
        print("\n1. Mark items from last 24 hours as ready for AI")
        print("2. Mark items from last 48 hours as ready for AI")
        print("3. Mark items from last 7 days as ready for AI")
        print("4. Mark ALL scraped items as ready for AI")
        print("5. Reset items that failed AI processing")
        print("6. Show stats only (no changes)")
        print("0. Exit")
        print()

        choice = input("Select an option: ").strip()

        if choice == "1":
            await mark_ready_for_ai(conn, 24)
        elif choice == "2":
            await mark_ready_for_ai(conn, 48)
        elif choice == "3":
            await mark_ready_for_ai(conn, 24 * 7)
        elif choice == "4":
            confirm = input("Are you sure you want to mark ALL items? (yes/no): ")
            if confirm.lower() == "yes":
                await mark_all_scraped(conn)
            else:
                print("Cancelled")
        elif choice == "5":
            await reset_failed_items(conn)
        elif choice == "6":
            print("\nNo changes made")
        elif choice == "0":
            print("\nExiting...")
        else:
            print("\nInvalid option")

        # Show updated stats
        if choice in ["1", "2", "3", "4", "5"]:
            await show_stats(conn)

    finally:
        await conn.close()
        print("\n[OK] Connection closed")


if __name__ == "__main__":
    asyncio.run(main())
