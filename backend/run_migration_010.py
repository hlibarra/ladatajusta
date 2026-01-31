"""
Run migration 010: Create site_config table
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
import asyncpg

# Load environment variables
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "ladatajusta"),
    "user": os.getenv("DB_USER", "ladatajusta"),
    "password": os.getenv("DB_PASSWORD", "ladatajusta"),
}

async def run_migration():
    print(f"Connecting to database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # Read migration file
        migration_path = Path(__file__).parent / "migrations" / "010_create_site_config.sql"
        with open(migration_path, 'r', encoding='utf-8') as f:
            sql = f.read()

        print("Running migration 010: Create site_config table...")
        await conn.execute(sql)
        print("Migration completed successfully!")

        # Verify
        result = await conn.fetch("SELECT key, value, description FROM site_config")
        print(f"\nConfigurations created: {len(result)}")
        for row in result:
            print(f"  - {row['key']}: {row['value']} ({row['description'][:50]}...)")

    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run_migration())
