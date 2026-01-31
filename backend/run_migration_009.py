"""Run migration 009 - Add AI prompt to sources"""

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
    """Run migration"""

    print("=" * 80)
    print("Running migration 009: Add AI prompt to sources")
    print("=" * 80)

    # Read migration file
    migration_path = Path(__file__).parent / "migrations" / "009_add_ai_prompt_to_sources.sql"

    with open(migration_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Connect to database
    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        print("\nExecuting migration...")
        await conn.execute(sql_content)
        print("✓ Migration executed successfully")

        # Verify column was added
        column_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = 'scraping_sources'
                AND column_name = 'ai_prompt'
            );
            """
        )

        if column_exists:
            print("✓ Column 'ai_prompt' added to scraping_sources")
        else:
            print("✗ Column 'ai_prompt' was not added")

        # Show sources with prompts
        sources = await conn.fetch(
            """
            SELECT slug, name,
                   CASE WHEN ai_prompt IS NOT NULL
                        THEN LENGTH(ai_prompt)
                        ELSE 0
                   END as prompt_length
            FROM scraping_sources
            ORDER BY name
            """
        )

        print("\nSources with AI prompts:")
        print("-" * 80)
        for source in sources:
            status = f"{source['prompt_length']} chars" if source['prompt_length'] > 0 else "No prompt"
            print(f"  {source['name']:20} ({source['slug']:15}) - {status}")
        print("-" * 80)

    finally:
        await conn.close()
        print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
