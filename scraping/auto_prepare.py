"""
Auto-Prepare Module for La Data Justa

Analyzes AI-processed items and marks high-quality, non-duplicate
items as "ready_to_publish" for quick human review.

Quality Filters:
1. Valid AI title (min 20 chars)
2. Valid AI summary (min 50 chars)
3. Valid AI category
4. Has reading levels content
5. Not a duplicate of existing publications

Duplicate Detection:
- Compares ai_title against published titles using similarity
- Uses PostgreSQL trigram similarity (pg_trgm)
- Threshold: 0.6 similarity = likely duplicate
"""

import asyncio
import asyncpg
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / "lagaceta" / ".env"
load_dotenv(dotenv_path=env_path)

# Database connection
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "ladatajusta"),
    "user": os.getenv("DB_USER", "ladatajusta"),
    "password": os.getenv("DB_PASSWORD", "ladatajusta"),
}

# Quality thresholds
MIN_TITLE_LENGTH = 20
MIN_SUMMARY_LENGTH = 50
MIN_CONTENT_LENGTH = 100
SIMILARITY_THRESHOLD = 0.6  # 0.6 = 60% similar = duplicate

# Expiration thresholds (in hours)
EXPIRE_READY_TO_PUBLISH_HOURS = int(os.getenv("EXPIRE_READY_HOURS", "12"))
EXPIRE_AI_COMPLETED_HOURS = int(os.getenv("EXPIRE_AI_COMPLETED_HOURS", "24"))

# Valid categories
VALID_CATEGORIES = [
    "Ciencia", "Cultura", "Deportes", "Economía", "Educación",
    "Investigación", "Medio Ambiente", "Política", "Salud",
    "Sociedad", "Tecnología", "Turismo"
]


def log(message: str, level: str = "INFO"):
    """Log with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


async def ensure_trigram_extension(conn):
    """Ensure pg_trgm extension is available for similarity matching"""
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    except Exception as e:
        log(f"Note: pg_trgm extension: {e}", "WARN")


async def get_ai_completed_items(conn, limit: int = 50):
    """Get items that have completed AI processing and need quality review"""
    rows = await conn.fetch(
        """
        SELECT
            id,
            source_media,
            source_section,
            source_url,
            ai_title,
            ai_summary,
            ai_category,
            ai_tags,
            ai_metadata,
            content,
            article_date
        FROM scraping_items
        WHERE status = 'ai_completed'
        ORDER BY ai_processed_at DESC
        LIMIT $1
        """,
        limit
    )
    return [dict(row) for row in rows]


async def check_duplicate_by_title(conn, ai_title: str, item_id: str) -> dict | None:
    """
    Check if a similar title already exists in publications.
    Returns the matching publication if found, None otherwise.
    """
    if not ai_title:
        return None

    # Use trigram similarity to find similar titles
    row = await conn.fetchrow(
        """
        SELECT
            id,
            title,
            similarity(LOWER(title), LOWER($1)) as sim
        FROM publications
        WHERE state = 'published'
          AND similarity(LOWER(title), LOWER($1)) > $2
        ORDER BY sim DESC
        LIMIT 1
        """,
        ai_title,
        SIMILARITY_THRESHOLD
    )

    if row:
        return {
            "publication_id": str(row["id"]),
            "title": row["title"],
            "similarity": float(row["sim"])
        }

    # Also check against other scraping items that are ready_to_publish or published
    row = await conn.fetchrow(
        """
        SELECT
            id,
            ai_title,
            similarity(LOWER(ai_title), LOWER($1)) as sim
        FROM scraping_items
        WHERE id != $2
          AND status IN ('ready_to_publish', 'published')
          AND ai_title IS NOT NULL
          AND similarity(LOWER(ai_title), LOWER($1)) > $3
        ORDER BY sim DESC
        LIMIT 1
        """,
        ai_title,
        item_id,
        SIMILARITY_THRESHOLD
    )

    if row:
        return {
            "scraping_item_id": str(row["id"]),
            "title": row["ai_title"],
            "similarity": float(row["sim"])
        }

    return None


def validate_quality(item: dict) -> tuple[bool, str]:
    """
    Validate item quality.
    Returns (is_valid, reason)
    """
    import json

    ai_title = item.get("ai_title") or ""
    ai_summary = item.get("ai_summary") or ""
    ai_category = item.get("ai_category") or ""
    ai_metadata = item.get("ai_metadata") or {}
    content = item.get("content") or ""

    # Parse ai_metadata if it's a string
    if isinstance(ai_metadata, str):
        try:
            ai_metadata = json.loads(ai_metadata)
        except (json.JSONDecodeError, TypeError):
            ai_metadata = {}

    # Check title
    if len(ai_title.strip()) < MIN_TITLE_LENGTH:
        return False, f"Título muy corto ({len(ai_title)} chars, min {MIN_TITLE_LENGTH})"

    # Check summary
    if len(ai_summary.strip()) < MIN_SUMMARY_LENGTH:
        return False, f"Resumen muy corto ({len(ai_summary)} chars, min {MIN_SUMMARY_LENGTH})"

    # Check category
    if ai_category not in VALID_CATEGORIES:
        return False, f"Categoría inválida: {ai_category}"

    # Check reading levels exist
    sin_vueltas = ai_metadata.get("sin_vueltas") or ""
    lo_central = ai_metadata.get("lo_central") or ""
    en_profundidad = ai_metadata.get("en_profundidad") or ""

    if not sin_vueltas or len(sin_vueltas) < 20:
        return False, "Falta contenido 'Sin vueltas'"

    if not lo_central or len(lo_central) < 50:
        return False, "Falta contenido 'Lo central'"

    if not en_profundidad or len(en_profundidad) < MIN_CONTENT_LENGTH:
        return False, f"Contenido 'En profundidad' muy corto ({len(en_profundidad)} chars)"

    # Check original content length
    if len(content.strip()) < MIN_CONTENT_LENGTH:
        return False, f"Contenido original muy corto ({len(content)} chars)"

    # Check if AI marked as invalid
    if ai_metadata.get("is_valid") == False:
        return False, ai_metadata.get("validation_reason", "AI marcó como inválido")

    return True, "OK"


async def update_item_status(conn, item_id: str, status: str, message: str):
    """Update item status"""
    await conn.execute(
        """
        UPDATE scraping_items
        SET status = $1,
            status_message = $2,
            status_updated_at = NOW(),
            updated_at = NOW()
        WHERE id = $3
        """,
        status,
        message,
        item_id
    )


async def process_item(conn, item: dict) -> dict:
    """
    Process a single item through quality and duplicate checks.
    Returns result dict with action taken.
    """
    item_id = str(item["id"])
    ai_title = item.get("ai_title") or "(Sin título)"

    result = {
        "id": item_id,
        "title": ai_title[:60],
        "action": None,
        "reason": None
    }

    # Step 1: Quality validation
    is_valid, quality_reason = validate_quality(item)

    if not is_valid:
        result["action"] = "quality_failed"
        result["reason"] = quality_reason
        # Keep as ai_completed but add note - don't mark as error
        await update_item_status(
            conn, item_id,
            "ai_completed",
            f"Auto-prepare: calidad insuficiente - {quality_reason}"
        )
        return result

    # Step 2: Duplicate check
    duplicate = await check_duplicate_by_title(conn, item.get("ai_title"), item_id)

    if duplicate:
        result["action"] = "duplicate"
        result["reason"] = f"Similar a: {duplicate['title'][:40]}... ({duplicate['similarity']:.0%})"
        await update_item_status(
            conn, item_id,
            "duplicate",
            f"Duplicado detectado: {duplicate['similarity']:.0%} similar a '{duplicate['title'][:60]}'"
        )
        return result

    # Step 3: Mark as ready to publish
    result["action"] = "ready_to_publish"
    result["reason"] = "Pasó filtros de calidad y no es duplicado"

    # Build detailed approval message
    ai_title = item.get("ai_title") or ""
    ai_summary = item.get("ai_summary") or ""
    ai_category = item.get("ai_category") or ""
    approval_msg = f"✓ Título: {len(ai_title)}ch, Resumen: {len(ai_summary)}ch, Cat: {ai_category}, Sin duplicados"

    await update_item_status(
        conn, item_id,
        "ready_to_publish",
        approval_msg
    )

    return result


async def cleanup_expired_items(conn) -> dict:
    """
    Expire old items that were not reviewed in time.
    - ready_to_publish > X hours → expired
    - ai_completed > X hours → discarded
    """
    stats = {"expired": 0, "discarded": 0}

    # Expire items in ready_to_publish that are too old
    result = await conn.execute(
        """
        UPDATE scraping_items
        SET status = 'expired',
            status_message = $1,
            status_updated_at = NOW(),
            updated_at = NOW()
        WHERE status = 'ready_to_publish'
          AND status_updated_at < NOW() - INTERVAL '1 hour' * $2
        """,
        f"Auto-expirado: más de {EXPIRE_READY_TO_PUBLISH_HOURS}hs sin revisar",
        EXPIRE_READY_TO_PUBLISH_HOURS
    )
    if result:
        count = int(result.split()[-1]) if result else 0
        stats["expired"] = count

    # Discard items in ai_completed that failed quality and are too old
    result = await conn.execute(
        """
        UPDATE scraping_items
        SET status = 'discarded',
            status_message = $1,
            status_updated_at = NOW(),
            updated_at = NOW()
        WHERE status = 'ai_completed'
          AND status_updated_at < NOW() - INTERVAL '1 hour' * $2
        """,
        f"Auto-descartado: más de {EXPIRE_AI_COMPLETED_HOURS}hs en cola",
        EXPIRE_AI_COMPLETED_HOURS
    )
    if result:
        count = int(result.split()[-1]) if result else 0
        stats["discarded"] = count

    return stats


async def main():
    """Main function"""
    log("=" * 60)
    log("AUTO-PREPARE: Preparación automática de items")
    log("=" * 60)
    log(f"Filtros de calidad:")
    log(f"  - Título mínimo: {MIN_TITLE_LENGTH} chars")
    log(f"  - Resumen mínimo: {MIN_SUMMARY_LENGTH} chars")
    log(f"  - Umbral de duplicado: {SIMILARITY_THRESHOLD:.0%}")
    log(f"Expiración:")
    log(f"  - ready_to_publish > {EXPIRE_READY_TO_PUBLISH_HOURS}hs → expired")
    log(f"  - ai_completed > {EXPIRE_AI_COMPLETED_HOURS}hs → discarded")

    # Connect to database
    log("\nConectando a base de datos...")
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        log("Conexión exitosa")
    except Exception as e:
        log(f"Error de conexión: {e}", "ERROR")
        return {"processed": 0, "ready": 0, "duplicates": 0, "quality_failed": 0}

    try:
        # Ensure trigram extension
        await ensure_trigram_extension(conn)

        # Get items to process
        items = await get_ai_completed_items(conn, limit=100)

        if not items:
            log("No hay items para procesar")
            return {"processed": 0, "ready": 0, "duplicates": 0, "quality_failed": 0}

        log(f"\nProcesando {len(items)} items...")

        # Process each item
        stats = {
            "processed": 0,
            "ready": 0,
            "duplicates": 0,
            "quality_failed": 0
        }

        for i, item in enumerate(items, 1):
            result = await process_item(conn, item)
            stats["processed"] += 1

            if result["action"] == "ready_to_publish":
                stats["ready"] += 1
                log(f"  [{i}] LISTO: {result['title']}...")
            elif result["action"] == "duplicate":
                stats["duplicates"] += 1
                log(f"  [{i}] DUPLICADO: {result['title']}... - {result['reason']}")
            elif result["action"] == "quality_failed":
                stats["quality_failed"] += 1
                log(f"  [{i}] CALIDAD: {result['title']}... - {result['reason']}")

        # Cleanup expired items
        log("\nLimpiando items viejos...")
        cleanup_stats = await cleanup_expired_items(conn)
        stats["expired"] = cleanup_stats["expired"]
        stats["auto_discarded"] = cleanup_stats["discarded"]

        if cleanup_stats["expired"] > 0 or cleanup_stats["discarded"] > 0:
            log(f"  Expirados (ready_to_publish > {EXPIRE_READY_TO_PUBLISH_HOURS}hs): {cleanup_stats['expired']}")
            log(f"  Descartados (ai_completed > {EXPIRE_AI_COMPLETED_HOURS}hs): {cleanup_stats['discarded']}")

        # Summary
        log("\n" + "=" * 60)
        log("RESUMEN")
        log("=" * 60)
        log(f"Procesados: {stats['processed']}")
        log(f"Listos para publicar: {stats['ready']}")
        log(f"Duplicados descartados: {stats['duplicates']}")
        log(f"Calidad insuficiente: {stats['quality_failed']}")
        log(f"Expirados: {stats.get('expired', 0)}")
        log(f"Auto-descartados: {stats.get('auto_discarded', 0)}")

        return stats

    finally:
        await conn.close()
        log("\nConexión cerrada")


if __name__ == "__main__":
    asyncio.run(main())
