"""
AI Processing Agent for Scraped Items
Processes scraped articles using OpenAI to generate:
- Improved titles
- Optimized summaries
- Categories and tags
- Content validation
"""

import asyncio
import asyncpg
import os
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Load environment variables
# In Docker: uses env vars passed by docker-compose
# Locally: searches for .env in parent directories (finds root .env)
load_dotenv()

# Reconfigure stdout for Windows emoji support
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

# OpenAI configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Valid categories based on existing publications
VALID_CATEGORIES = [
    "Ciencia", "Cultura", "Deportes", "Economía", "Educación",
    "Investigación", "Medio Ambiente", "Política", "Salud",
    "Sociedad", "Tecnología", "Turismo"
]

# Processing configuration
CONCURRENCY = 3  # Process 3 items at a time
PROMPT_VERSION = "2.0.0"  # Updated to include 3 reading levels

# Image generation configuration
# Changed to false by default - images are now generated on-demand via API endpoint
GENERATE_IMAGES = os.getenv("GENERATE_IMAGES", "false").lower() == "true"
DALLE_MODEL = "dall-e-3"
DALLE_SIZE = "1024x1024"
DALLE_QUALITY = "standard"  # standard or hd

# Initialize OpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def create_processing_prompt(item: dict, custom_prompt: str | None = None) -> str:
    """Create the prompt for AI processing"""

    # If custom prompt provided, use it with variable substitution
    if custom_prompt:
        return custom_prompt.format(
            title=item.get('title', 'Sin título'),
            summary=item.get('summary', 'Sin resumen'),
            source_section=item.get('source_section', 'Sin sección'),
            content=item.get('content', '')[:3000]
        )

    # Default prompt
    categories_str = ", ".join(VALID_CATEGORIES)

    prompt = f"""Eres un editor periodístico profesional de "La Data Justa", un medio innovador que ofrece tres niveles de profundidad para cada noticia.

Analiza el siguiente artículo y genera:

1. **Título mejorado**: Versión más atractiva y periodística, máximo 100 caracteres
2. **Resumen**: Resumen conciso para lista de noticias (150-200 caracteres)
3. **Sin vueltas**: Ultra breve, 1-2 oraciones directas (40-60 palabras)
4. **Lo central**: Párrafo esencial con lo más importante (80-120 palabras)
5. **En profundidad**: Versión completa con contexto y detalles (200-300 palabras)
6. **Categoría**: Una sola de: {categories_str}
7. **Tags**: 3-5 etiquetas relevantes
8. **Validación**: ¿Es contenido relevante y publicable?

ARTÍCULO ORIGINAL:
---
Título: {item.get('title', 'Sin título')}
Resumen: {item.get('summary', 'Sin resumen')}
Sección: {item.get('source_section', 'Sin sección')}

Contenido:
{item.get('content', '')[:3000]}
---

Responde SOLO con un JSON válido en este formato exacto:
{{
    "title": "título mejorado aquí",
    "summary": "resumen para lista",
    "sin_vueltas": "1-2 oraciones ultra directas",
    "lo_central": "párrafo esencial con lo más importante",
    "en_profundidad": "versión completa con contexto y análisis",
    "category": "categoría aquí",
    "tags": ["tag1", "tag2", "tag3"],
    "is_valid": true,
    "validation_reason": "explicación si is_valid es false"
}}"""

    return prompt


async def process_item_with_ai(item: dict, custom_prompt: str | None = None) -> dict | None:
    """Process a single item with OpenAI"""

    if not client:
        print("[ERROR] OpenAI client not initialized. Set OPENAI_API_KEY environment variable.")
        return None

    start_time = time.time()

    try:
        prompt = create_processing_prompt(item, custom_prompt)

        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Eres un editor periodístico profesional. Respondes solo con JSON válido."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=1500,  # Increased for 3 reading levels
            response_format={"type": "json_object"}
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # Parse AI response
        ai_content = response.choices[0].message.content
        ai_data = json.loads(ai_content)

        # Calculate cost (approximate for gpt-4o-mini)
        # Input: $0.150 per 1M tokens, Output: $0.600 per 1M tokens
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        cost_usd = (input_tokens * 0.150 / 1_000_000) + (output_tokens * 0.600 / 1_000_000)

        return {
            "ai_title": ai_data.get("title"),
            "ai_summary": ai_data.get("summary"),
            "ai_category": ai_data.get("category"),
            "ai_tags": ai_data.get("tags", []),
            "ai_model": OPENAI_MODEL,
            "ai_prompt_version": PROMPT_VERSION,
            "ai_tokens_used": total_tokens,
            "ai_cost_usd": cost_usd,
            "ai_processing_duration_ms": duration_ms,
            "ai_metadata": {
                "is_valid": ai_data.get("is_valid", True),
                "validation_reason": ai_data.get("validation_reason"),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                # Three reading levels
                "sin_vueltas": ai_data.get("sin_vueltas"),
                "lo_central": ai_data.get("lo_central"),
                "en_profundidad": ai_data.get("en_profundidad"),
            },
            "is_valid": ai_data.get("is_valid", True)
        }

    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse AI response as JSON: {e}")
        return None
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        # Check for common OpenAI errors
        if "rate_limit" in error_msg.lower() or "429" in error_msg:
            print(f"[ERROR] OpenAI rate limit exceeded: {error_msg}")
        elif "timeout" in error_msg.lower():
            print(f"[ERROR] OpenAI timeout: {error_msg}")
        elif "api_key" in error_msg.lower():
            print(f"[ERROR] OpenAI API key issue: {error_msg}")
        else:
            print(f"[ERROR] AI processing failed ({error_type}): {error_msg}")
        return None


async def generate_article_image(ai_title: str, ai_category: str, sin_vueltas: str) -> dict | None:
    """Generate a unique image for the article using DALL-E 3"""

    if not client:
        print("[ERROR] OpenAI client not initialized")
        return None

    if not GENERATE_IMAGES:
        print("[INFO] Image generation disabled")
        return None

    start_time = time.time()

    try:
        # Create image prompt based on article content
        image_prompt = f"""Ilustración editorial minimalista para artículo periodístico.

Categoría: {ai_category}
Título: {ai_title}
Concepto: {sin_vueltas}

Estilo: Ilustración moderna y abstracta, colores planos, diseño editorial limpio, composición equilibrada.
NO incluir texto, NO incluir personas reconocibles, enfoque conceptual y simbólico."""

        # Truncate if too long (DALL-E has a 4000 char limit)
        if len(image_prompt) > 1000:
            image_prompt = image_prompt[:1000]

        print(f"    [IMAGE] Generating with DALL-E 3...")

        response = await client.images.generate(
            model=DALLE_MODEL,
            prompt=image_prompt,
            size=DALLE_SIZE,
            quality=DALLE_QUALITY,
            n=1
        )

        duration_ms = int((time.time() - start_time) * 1000)

        image_url = response.data[0].url
        revised_prompt = response.data[0].revised_prompt

        # DALL-E 3 pricing (as of 2025):
        # Standard 1024x1024: $0.040 per image
        # HD 1024x1024: $0.080 per image
        cost_usd = 0.080 if DALLE_QUALITY == "hd" else 0.040

        print(f"    [IMAGE] Generated in {duration_ms}ms")
        print(f"    [IMAGE] URL: {image_url[:60]}...")
        print(f"    [IMAGE] Cost: ${cost_usd:.3f}")

        return {
            "image_url": image_url,
            "revised_prompt": revised_prompt,
            "model": DALLE_MODEL,
            "size": DALLE_SIZE,
            "quality": DALLE_QUALITY,
            "cost_usd": cost_usd,
            "duration_ms": duration_ms
        }

    except Exception as e:
        print(f"[ERROR] Image generation failed: {e}")
        return None


async def update_item_with_ai_data(conn, item_id: str, ai_data: dict, is_valid: bool):
    """Update scraping item with AI-generated data"""

    try:
        # Determine new status
        if is_valid:
            new_status = "ai_completed"
            status_message = "AI processing completed successfully"
        else:
            new_status = "discarded"
            status_message = f"Discarded: {ai_data['ai_metadata'].get('validation_reason', 'Not valid')}"

        # Include image URLs if available
        image_urls = ai_data.get("image_urls", [])

        await conn.execute(
            """
            UPDATE scraping_items
            SET
                ai_title = $1,
                ai_summary = $2,
                ai_category = $3,
                ai_tags = $4,
                ai_model = $5,
                ai_prompt_version = $6,
                ai_tokens_used = $7,
                ai_cost_usd = $8,
                ai_processed_at = NOW(),
                ai_processing_duration_ms = $9,
                ai_metadata = $10,
                status = $11,
                status_message = $12,
                image_urls = $13,
                status_updated_at = NOW(),
                updated_at = NOW()
            WHERE id = $14
            """,
            ai_data["ai_title"],
            ai_data["ai_summary"],
            ai_data["ai_category"],
            ai_data["ai_tags"],
            ai_data["ai_model"],
            ai_data["ai_prompt_version"],
            ai_data["ai_tokens_used"],
            ai_data["ai_cost_usd"],
            ai_data["ai_processing_duration_ms"],
            json.dumps(ai_data["ai_metadata"]),
            new_status,
            status_message,
            image_urls,
            item_id
        )

        return True

    except Exception as e:
        print(f"[ERROR] Failed to update item {item_id}: {e}")
        return False


async def get_source_prompt(conn, source_media: str) -> str | None:
    """Get AI prompt for a specific source"""

    row = await conn.fetchrow(
        """
        SELECT ai_prompt
        FROM scraping_sources
        WHERE media_type = $1 AND is_active = true
        """,
        source_media
    )

    return row['ai_prompt'] if row and row['ai_prompt'] else None


async def get_items_to_process(conn, limit: int = 20):
    """Get items ready for AI processing"""

    rows = await conn.fetch(
        """
        SELECT
            id,
            source_media,
            source_section,
            source_url,
            title,
            subtitle,
            summary,
            content,
            article_date
        FROM scraping_items
        WHERE status IN ('scraped', 'ready_for_ai')
          AND retry_count < max_retries
        ORDER BY article_date DESC NULLS LAST
        LIMIT $1
        """,
        limit
    )

    return [dict(row) for row in rows]


async def process_single_item(conn, item: dict, index: int, total: int) -> dict:
    """Process a single item. Returns dict with success status and item_id."""

    item_id = str(item['id'])
    title = item.get('title', 'Sin título')[:60]
    source_media = item.get('source_media', 'unknown')

    print(f"\n[{index}/{total}] Processing: {title}...")
    print(f"    ID: {item_id[:8]}...")
    print(f"    Source: {source_media}")
    print(f"    Section: {item.get('source_section', 'Unknown')}")

    # Get custom prompt for this source
    custom_prompt = await get_source_prompt(conn, source_media)
    if custom_prompt:
        print(f"    [INFO] Using custom prompt for {source_media}")

    # Process with AI
    ai_data = await process_item_with_ai(item, custom_prompt)

    if not ai_data:
        print(f"    [ERROR] AI processing failed")
        # Update retry count
        await conn.execute(
            """
            UPDATE scraping_items
            SET retry_count = retry_count + 1,
                last_error = 'AI processing failed',
                last_error_at = NOW()
            WHERE id = $1
            """,
            item_id
        )
        return {"success": False, "item_id": item_id, "error": "AI processing failed"}

    # Generate image if content is valid
    if ai_data["is_valid"] and GENERATE_IMAGES:
        sin_vueltas = ai_data['ai_metadata'].get('sin_vueltas', '')
        image_data = await generate_article_image(
            ai_data['ai_title'],
            ai_data['ai_category'],
            sin_vueltas
        )

        if image_data:
            # Add image URL to ai_data
            ai_data["image_urls"] = [image_data["image_url"]]
            # Add image cost to total cost
            ai_data["ai_cost_usd"] += image_data["cost_usd"]
            # Store image metadata
            ai_data["ai_metadata"]["image_generation"] = {
                "model": image_data["model"],
                "size": image_data["size"],
                "quality": image_data["quality"],
                "revised_prompt": image_data["revised_prompt"],
                "cost_usd": image_data["cost_usd"],
                "duration_ms": image_data["duration_ms"]
            }
        else:
            ai_data["image_urls"] = []
    else:
        ai_data["image_urls"] = []

    # Update database
    success = await update_item_with_ai_data(conn, item_id, ai_data, ai_data["is_valid"])

    if success:
        if ai_data["is_valid"]:
            print(f"    [OK] AI Title: {ai_data['ai_title'][:60]}...")
            print(f"    [OK] Category: {ai_data['ai_category']}")
            print(f"    [OK] Tags: {', '.join(ai_data['ai_tags'][:3])}")
            # Show preview of reading levels
            sin_vueltas = ai_data['ai_metadata'].get('sin_vueltas', '')
            print(f"    [OK] Sin vueltas: {sin_vueltas[:80]}..." if len(sin_vueltas) > 80 else f"    [OK] Sin vueltas: {sin_vueltas}")
            # Show image info if generated
            if ai_data.get("image_urls"):
                print(f"    [OK] Image: Generated ({len(ai_data['image_urls'])} image)")
            print(f"    [OK] Tokens: {ai_data['ai_tokens_used']}, Total Cost: ${ai_data['ai_cost_usd']:.6f}")
        else:
            print(f"    [DISCARD] Reason: {ai_data['ai_metadata'].get('validation_reason')}")
        return {"success": True, "item_id": item_id}
    else:
        print(f"    [ERROR] Failed to update database")
        return {"success": False, "item_id": item_id, "error": "Failed to update database"}


async def main():
    """Main function"""

    print("=" * 70)
    print("[START] AI Processing Agent for La Data Justa")
    print("=" * 70)
    print(f"Model: {OPENAI_MODEL}")
    print(f"Prompt Version: {PROMPT_VERSION}")
    print(f"Concurrency: {CONCURRENCY}")
    print(f"Image Generation: {'Enabled' if GENERATE_IMAGES else 'Disabled'}")
    if GENERATE_IMAGES:
        print(f"  DALL-E Model: {DALLE_MODEL}")
        print(f"  Size: {DALLE_SIZE}")
        print(f"  Quality: {DALLE_QUALITY}")

    # Check OpenAI API key
    if not OPENAI_API_KEY:
        print("\n[ERROR] OPENAI_API_KEY environment variable not set!")
        print("Please set it before running this script.")
        return

    # Connect to database using pool for concurrent operations
    print("\n[DB] Connecting to PostgreSQL...")
    try:
        pool = await asyncpg.create_pool(**DB_CONFIG, min_size=CONCURRENCY, max_size=CONCURRENCY + 2)
        print("[DB] Connection pool created successfully")
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        return

    try:
        # Get items to process
        print("\n[FETCH] Getting items to process...")
        async with pool.acquire() as conn:
            items = await get_items_to_process(conn, limit=50)

        if not items:
            print("[INFO] No items to process")
            return

        print(f"[FETCH] Found {len(items)} items to process")

        # Process items with concurrency control
        total = len(items)
        successful = 0
        failed = 0

        # Process in batches - each task gets its own connection from pool
        for i in range(0, total, CONCURRENCY):
            batch = items[i:i + CONCURRENCY]
            batch_item_ids = [str(item['id']) for item in batch]

            async def process_with_pool_conn(item, index, total):
                async with pool.acquire() as conn:
                    return await process_single_item(conn, item, index, total)

            tasks = [
                process_with_pool_conn(item, i + j + 1, total)
                for j, item in enumerate(batch)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for idx, result in enumerate(results):
                item_id = batch_item_ids[idx]
                if isinstance(result, Exception):
                    # Log the actual exception
                    error_msg = str(result)[:500]
                    print(f"    [EXCEPTION] Item {item_id[:8]}...: {error_msg}")
                    failed += 1
                    # Update the item in database with the error
                    try:
                        async with pool.acquire() as conn:
                            await conn.execute(
                                """
                                UPDATE scraping_items
                                SET retry_count = retry_count + 1,
                                    last_error = $1,
                                    last_error_at = NOW()
                                WHERE id = $2
                                """,
                                f"Exception: {error_msg}",
                                item_id
                            )
                    except Exception as db_err:
                        print(f"    [ERROR] Failed to update error in DB: {db_err}")
                elif isinstance(result, dict) and result.get("success"):
                    successful += 1
                else:
                    failed += 1
                    # If result is a dict with error info, it was already logged/updated in process_single_item

            # Small delay between batches
            if i + CONCURRENCY < total:
                await asyncio.sleep(1)

        # Summary
        print("\n" + "=" * 70)
        print("[DONE] Processing completed")
        print("=" * 70)
        print(f"Total items: {total}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")

        # Get stats
        async with pool.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'ai_completed') as completed,
                    COUNT(*) FILTER (WHERE status = 'discarded') as discarded,
                    COALESCE(SUM(ai_tokens_used), 0) as total_tokens,
                    COALESCE(SUM(ai_cost_usd), 0) as total_cost
                FROM scraping_items
                WHERE ai_processed_at >= NOW() - INTERVAL '1 hour'
                """
            )

        print(f"\nRecent AI Stats (last hour):")
        print(f"  Completed: {stats['completed']}")
        print(f"  Discarded: {stats['discarded']}")
        print(f"  Total tokens: {stats['total_tokens']}")
        print(f"  Total cost: ${stats['total_cost']:.6f}")

        return {
            "processed": successful,
            "failed": failed,
            "total": total
        }

    finally:
        await pool.close()
        print("\n[DB] Connection pool closed")


if __name__ == "__main__":
    asyncio.run(main())
