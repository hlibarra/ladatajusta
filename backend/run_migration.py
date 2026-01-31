"""
Simple migration runner script
Executes a SQL migration file using asyncpg
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from scraping/.env
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


async def run_migration(migration_file: str):
    """Execute a SQL migration file"""

    # Read migration file
    migration_path = Path(__file__).parent / "migrations" / migration_file

    if not migration_path.exists():
        print(f"[ERROR] Migration file not found: {migration_path}")
        return False

    print(f"[INFO] Reading migration file: {migration_file}")
    with open(migration_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Connect to database
    print(f"[INFO] Connecting to database: {DB_CONFIG['database']}")
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        print("[OK] Connected successfully")
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        return False

    try:
        # Execute migration
        print(f"[INFO] Executing migration...")
        await conn.execute(sql_content)
        print("[OK] Migration executed successfully")

        # Verify table was created
        result = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'scraping_sources'
            );
            """
        )

        if result:
            print("[OK] Table 'scraping_sources' created and verified")

            # Count records
            count = await conn.fetchval("SELECT COUNT(*) FROM scraping_sources")
            print(f"[INFO] Found {count} scraping sources in table")
        else:
            print("[WARNING] Table 'scraping_sources' not found after migration")

        return True

    except Exception as e:
        print(f"[ERROR] Failed to execute migration: {e}")
        return False
    finally:
        await conn.close()
        print("[INFO] Database connection closed")


async def main():
    """Main function"""

    if len(sys.argv) > 1:
        migration_file = sys.argv[1]
    else:
        migration_file = "008_create_scraping_sources.sql"

    print("=" * 70)
    print("Migration Runner - La Data Justa")
    print("=" * 70)
    print(f"Migration: {migration_file}")
    print("=" * 70)

    success = await run_migration(migration_file)

    if success:
        print("\n[SUCCESS] Migration completed successfully!")
        return 0
    else:
        print("\n[FAILED] Migration failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
