#!/usr/bin/env python
"""
Script to run SQL migrations manually.
Usage: python run_migration.py 001_add_scraping_runs
"""
import sys
import os
import asyncio
import asyncpg
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings


async def run_migration(migration_name: str):
    """Run a SQL migration file"""
    migration_file = Path(__file__).parent / f"{migration_name}.sql"

    if not migration_file.exists():
        print(f"[ERROR] Migration file not found: {migration_file}")
        return False

    print(f"[INFO] Reading migration: {migration_file.name}")
    sql = migration_file.read_text()

    print(f"[INFO] Connecting to database...")
    # Convert SQLAlchemy URL to asyncpg format
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)

    try:
        print(f"[INFO] Executing migration...")
        await conn.execute(sql)
        print(f"[SUCCESS] Migration {migration_name} completed successfully!")
        return True
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        return False
    finally:
        await conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_migration.py <migration_name>")
        print("Example: python run_migration.py 001_add_scraping_runs")
        sys.exit(1)

    migration_name = sys.argv[1]
    success = asyncio.run(run_migration(migration_name))
    sys.exit(0 if success else 1)
