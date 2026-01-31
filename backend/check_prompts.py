"""Check AI prompts in sources"""

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
    """Check prompts"""

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        sources = await conn.fetch(
            """
            SELECT
                name,
                slug,
                is_active,
                CASE
                    WHEN ai_prompt IS NOT NULL THEN LENGTH(ai_prompt)
                    ELSE 0
                END as prompt_length
            FROM scraping_sources
            ORDER BY name
            """
        )

        print("=" * 80)
        print("AI Prompts en Fuentes")
        print("=" * 80)

        for source in sources:
            status = "ACTIVA" if source['is_active'] else "INACTIVA"
            prompt_status = f"{source['prompt_length']} caracteres" if source['prompt_length'] > 0 else "Sin prompt"

            print(f"\n{source['name']} ({source['slug']}) - {status}")
            print(f"  Prompt: {prompt_status}")

            if source['prompt_length'] > 0:
                # Show first 100 chars of prompt
                prompt = await conn.fetchval(
                    "SELECT ai_prompt FROM scraping_sources WHERE slug = $1",
                    source['slug']
                )
                print(f"  Preview: {prompt[:100]}...")

        print("\n" + "=" * 80)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
