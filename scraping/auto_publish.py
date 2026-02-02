"""
Auto-Publish Module for La Data Justa

Automatically publishes scraping items that:
1. Have status 'ready_to_publish'
2. Come from sources with auto_publish = true
3. Have been in ready_to_publish for at least auto_publish_delay_minutes

This provides a "review window" where admins can manually intervene
before items are automatically published.
"""

import asyncio
import asyncpg
import os
import re
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "ladatajusta"),
    "user": os.getenv("DB_USER", "ladatajusta"),
    "password": os.getenv("DB_PASSWORD", "ladatajusta"),
}

# Default delay (can be overridden per-source)
DEFAULT_AUTO_PUBLISH_DELAY_MINUTES = 15


def log(message: str, level: str = "INFO"):
    """Log with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug"""
    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and special chars with hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    # Remove leading/trailing hyphens
    text = text.strip('-')
    return text[:100]  # Limit length


async def get_items_to_publish(conn, limit: int = 50):
    """
    Get items ready for auto-publishing:
    - status = 'ready_to_publish'
    - source has auto_publish = true
    - enough time has passed (delay)
    """
    rows = await conn.fetch(
        """
        SELECT
            si.id,
            si.source_media,
            si.source_section,
            si.source_url,
            si.title,
            si.summary,
            si.content,
            si.author,
            si.article_date,
            si.tags,
            si.image_urls,
            si.video_urls,
            si.ai_title,
            si.ai_summary,
            si.ai_category,
            si.ai_tags,
            si.ai_metadata,
            si.status_updated_at,
            ss.id as source_id,
            ss.name as source_name,
            ss.auto_publish_delay_minutes
        FROM scraping_items si
        JOIN scraping_sources ss ON ss.slug = si.source_media
        WHERE si.status = 'ready_to_publish'
          AND ss.auto_publish = true
          AND si.status_updated_at <= NOW() - (ss.auto_publish_delay_minutes || ' minutes')::interval
          AND si.publication_id IS NULL
        ORDER BY si.status_updated_at ASC
        LIMIT $1
        """,
        limit
    )
    return [dict(row) for row in rows]


async def check_slug_exists(conn, slug: str) -> bool:
    """Check if a slug already exists in publications"""
    row = await conn.fetchrow(
        "SELECT 1 FROM publications WHERE slug = $1",
        slug
    )
    return row is not None


async def create_publication(conn, item: dict) -> dict:
    """
    Create a publication from a scraping item.
    Returns dict with publication_id and slug.
    """
    item_id = item["id"]

    # Determine content to use (AI-generated or original)
    title = item.get("ai_title") or item.get("title")
    summary = item.get("ai_summary") or item.get("summary") or ""
    body = item.get("content") or ""
    category = item.get("ai_category")
    tags = item.get("ai_tags") or item.get("tags") or []

    if not title:
        return {"error": "No title available"}

    # Generate slug
    slug_base = slugify(title)
    if not slug_base:
        slug_base = f"articulo-{str(item_id)[:8]}"

    # Check if slug exists, append UUID if needed
    if await check_slug_exists(conn, slug_base):
        slug_base = f"{slug_base}-{str(item_id)[:8]}"

    # Extract reading levels from ai_metadata
    ai_metadata = item.get("ai_metadata") or {}
    if isinstance(ai_metadata, str):
        import json
        try:
            ai_metadata = json.loads(ai_metadata)
        except (json.JSONDecodeError, TypeError):
            ai_metadata = {}

    content_sin_vueltas = ai_metadata.get("sin_vueltas")
    content_lo_central = ai_metadata.get("lo_central")
    content_en_profundidad = ai_metadata.get("en_profundidad")

    # Convert image_urls to media format
    media = []
    image_urls = item.get("image_urls") or []
    for idx, image_url in enumerate(image_urls):
        media.append({
            "type": "image",
            "url": image_url,
            "caption": "",
            "order": idx
        })

    # Generate new UUID for publication
    publication_id = uuid.uuid4()

    # Create publication
    await conn.execute(
        """
        INSERT INTO publications (
            id,
            scraping_item_id,
            agent_id,
            published_by_user_id,
            state,
            title,
            slug,
            summary,
            body,
            category,
            tags,
            content_sin_vueltas,
            content_lo_central,
            content_en_profundidad,
            media,
            published_at,
            origin_type,
            created_at
        ) VALUES (
            $1, $2, NULL, NULL, 'published',
            $3, $4, $5, $6, $7, $8,
            $9, $10, $11, $12,
            NOW(), 'detected_media', NOW()
        )
        """,
        publication_id,
        item_id,
        title,
        slug_base,
        summary,
        body,
        category,
        tags,
        content_sin_vueltas,
        content_lo_central,
        content_en_profundidad,
        media if media else []
    )

    # Update scraping item
    await conn.execute(
        """
        UPDATE scraping_items
        SET publication_id = $1,
            published_at = NOW(),
            status = 'published',
            status_message = 'Auto-publicado',
            status_updated_at = NOW(),
            updated_at = NOW()
        WHERE id = $2
        """,
        publication_id,
        item_id
    )

    return {
        "publication_id": str(publication_id),
        "slug": slug_base
    }


async def process_item(conn, item: dict) -> dict:
    """
    Process a single item for auto-publishing.
    Returns result dict with action taken.
    """
    item_id = str(item["id"])
    ai_title = item.get("ai_title") or item.get("title") or "(Sin título)"
    source_name = item.get("source_name", "Unknown")
    delay = item.get("auto_publish_delay_minutes", DEFAULT_AUTO_PUBLISH_DELAY_MINUTES)

    result = {
        "id": item_id,
        "title": ai_title[:60],
        "source": source_name,
        "delay_minutes": delay,
        "action": None,
        "reason": None
    }

    try:
        pub_result = await create_publication(conn, item)

        if "error" in pub_result:
            result["action"] = "error"
            result["reason"] = pub_result["error"]
            # Update status to indicate error
            await conn.execute(
                """
                UPDATE scraping_items
                SET status_message = $1,
                    status_updated_at = NOW()
                WHERE id = $2
                """,
                f"Auto-publish error: {pub_result['error']}",
                item["id"]
            )
        else:
            result["action"] = "published"
            result["publication_id"] = pub_result["publication_id"]
            result["slug"] = pub_result["slug"]
            result["reason"] = f"Auto-publicado exitosamente"

    except Exception as e:
        result["action"] = "error"
        result["reason"] = str(e)[:200]
        log(f"Error publishing item {item_id}: {e}", "ERROR")

    return result


async def main():
    """Main function"""
    log("=" * 60)
    log("AUTO-PUBLISH: Publicación automática de items")
    log("=" * 60)

    # Connect to database
    log("Conectando a base de datos...")
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        log("Conexión exitosa")
    except Exception as e:
        log(f"Error de conexión: {e}", "ERROR")
        return {"published": 0, "errors": 0}

    try:
        # Get items to publish
        items = await get_items_to_publish(conn, limit=50)

        if not items:
            log("No hay items para auto-publicar")
            return {"published": 0, "errors": 0}

        log(f"\nProcesando {len(items)} items para auto-publicar...")

        # Process each item
        stats = {
            "processed": 0,
            "published": 0,
            "errors": 0
        }

        for i, item in enumerate(items, 1):
            result = await process_item(conn, item)
            stats["processed"] += 1

            if result["action"] == "published":
                stats["published"] += 1
                log(f"  [{i}] PUBLICADO: {result['title']}... -> /{result['slug']}")
            elif result["action"] == "error":
                stats["errors"] += 1
                log(f"  [{i}] ERROR: {result['title']}... - {result['reason']}", "ERROR")

        # Summary
        log("\n" + "=" * 60)
        log("RESUMEN AUTO-PUBLISH")
        log("=" * 60)
        log(f"Procesados: {stats['processed']}")
        log(f"Publicados: {stats['published']}")
        log(f"Errores: {stats['errors']}")

        return stats

    finally:
        await conn.close()
        log("\nConexión cerrada")


if __name__ == "__main__":
    asyncio.run(main())
