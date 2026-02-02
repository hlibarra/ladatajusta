"""
News Curator - Intelligent News Selection and Publishing

Selects and publishes the best 10-15 news items from all ready_to_publish items
using an algorithm that prioritizes:
1. Category diversity - Mix of different categories
2. Source diversity - Mix of different media sources
3. Recency - Newer items preferred
4. No thematic duplicates - Avoids similar news stories
"""

import asyncio
import json
import os
import re
import sys
import unicodedata
import uuid as uuid_module
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Any, Optional
from uuid import UUID

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug"""
    if not text:
        return ""
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


async def get_ready_to_publish_items(pool) -> List[Dict[str, Any]]:
    """Get all items ready to publish with their source info and full data for publication"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                si.id,
                si.title,
                si.summary,
                si.content,
                si.source_url as original_url,
                COALESCE(si.ai_category, si.source_section, 'general') as category,
                si.source_media,
                si.scraped_at as created_at,
                si.status_updated_at as ai_processed_at,
                si.ai_title,
                si.ai_summary,
                si.ai_category,
                si.ai_tags,
                si.ai_metadata,
                si.image_urls,
                ss.name as source_name,
                ss.media_type,
                ss.id as source_id
            FROM scraping_items si
            LEFT JOIN scraping_sources ss ON si.source_media = ss.media_type
            WHERE si.status = 'ready_to_publish'
            ORDER BY si.scraped_at DESC
        """)
        return [dict(row) for row in rows]


def normalize_title(title: str) -> str:
    """Normalize title for comparison (remove common words, punctuation)"""
    if not title:
        return ""
    # Convert to lowercase and remove punctuation
    import re
    normalized = re.sub(r'[^\w\s]', '', title.lower())
    # Remove common Spanish words
    stop_words = {'el', 'la', 'los', 'las', 'un', 'una', 'de', 'del', 'en', 'con',
                  'por', 'para', 'que', 'y', 'a', 'su', 'se', 'es', 'al'}
    words = [w for w in normalized.split() if w not in stop_words and len(w) > 2]
    return ' '.join(words)


def calculate_similarity(title1: str, title2: str) -> float:
    """Calculate similarity between two titles (0-1)"""
    words1 = set(normalize_title(title1).split())
    words2 = set(normalize_title(title2).split())

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    return len(intersection) / len(union) if union else 0.0


def find_duplicates(items: List[Dict], threshold: float = 0.6) -> Dict[str, List[str]]:
    """Find groups of similar items (potential duplicates)"""
    duplicates = defaultdict(list)
    processed = set()

    for i, item1 in enumerate(items):
        if str(item1['id']) in processed:
            continue

        group = [str(item1['id'])]
        processed.add(str(item1['id']))

        for j, item2 in enumerate(items[i+1:], i+1):
            if str(item2['id']) in processed:
                continue

            similarity = calculate_similarity(item1['title'], item2['title'])
            if similarity >= threshold:
                group.append(str(item2['id']))
                processed.add(str(item2['id']))

        if len(group) > 1:
            # Use first item's id as the group key
            duplicates[group[0]] = group

    return duplicates


def select_best_from_duplicates(items: List[Dict], duplicate_groups: Dict[str, List[str]]) -> List[Dict]:
    """From each duplicate group, select the best item (most recent, prefer diverse sources)"""
    items_by_id = {str(item['id']): item for item in items}
    selected_ids = set()
    removed_ids = set()

    for group_key, group_ids in duplicate_groups.items():
        # Get items in this group
        group_items = [items_by_id[id] for id in group_ids if id in items_by_id]

        if not group_items:
            continue

        # Select the most recent one
        best = max(group_items, key=lambda x: x['created_at'])
        selected_ids.add(str(best['id']))

        # Mark others as removed
        for item in group_items:
            if str(item['id']) != str(best['id']):
                removed_ids.add(str(item['id']))

    # Return items that weren't removed
    return [item for item in items if str(item['id']) not in removed_ids]


def select_curated_items(items: List[Dict], target_count: int = 12,
                         max_per_category: int = 3, max_per_source: int = 3) -> List[Dict]:
    """
    Select curated items using the diversity algorithm:
    1. Remove duplicates (keep best from each group)
    2. Group by category
    3. From each category, take max items (prioritizing source diversity)
    4. Balance to reach target count
    """
    if not items:
        return []

    # Step 1: Find and remove duplicate news stories
    duplicate_groups = find_duplicates(items)
    items = select_best_from_duplicates(items, duplicate_groups)

    # Step 2: Group by category
    by_category = defaultdict(list)
    for item in items:
        category = item.get('category') or 'general'
        by_category[category].append(item)

    # Step 3: From each category, select items prioritizing source diversity
    selected = []
    category_counts = defaultdict(int)
    source_counts = defaultdict(int)

    # Use source_media as the key for source diversity (more reliable than source_id)
    def get_source_key(item):
        return item.get('source_media') or item.get('source_id') or 'unknown'

    # First pass: ensure at least one from each category (if available)
    categories = list(by_category.keys())
    for category in categories:
        cat_items = by_category[category]
        if cat_items:
            # Sort by date (newest first)
            cat_items.sort(key=lambda x: x['created_at'], reverse=True)
            # Pick the newest one
            item = cat_items[0]
            selected.append(item)
            category_counts[category] += 1
            source_counts[get_source_key(item)] += 1

    # Second pass: fill up to target_count, respecting limits
    all_remaining = []
    for category, cat_items in by_category.items():
        for item in cat_items:
            if item not in selected:
                all_remaining.append(item)

    # Sort remaining by date
    all_remaining.sort(key=lambda x: x['created_at'], reverse=True)

    for item in all_remaining:
        if len(selected) >= target_count:
            break

        category = item.get('category') or 'general'
        source_key = get_source_key(item)

        # Check limits
        if category_counts[category] >= max_per_category:
            continue
        if source_counts[source_key] >= max_per_source:
            continue

        selected.append(item)
        category_counts[category] += 1
        source_counts[source_key] += 1

    # If still under target, relax constraints and add more
    if len(selected) < target_count:
        for item in all_remaining:
            if len(selected) >= target_count:
                break
            if item not in selected:
                selected.append(item)

    return selected


async def check_slug_exists(conn, slug: str) -> bool:
    """Check if a slug already exists in publications"""
    row = await conn.fetchrow(
        "SELECT 1 FROM publications WHERE slug = $1",
        slug
    )
    return row is not None


async def create_publication(conn, item: dict) -> dict:
    """Create a publication from a scraping item"""
    item_id = item["id"]

    # Determine content to use (AI-generated or original)
    title = item.get("ai_title") or item.get("title")
    summary = item.get("ai_summary") or item.get("summary") or ""
    body = item.get("content") or ""
    category = item.get("ai_category") or item.get("category")
    tags = item.get("ai_tags") or []

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
    publication_id = uuid_module.uuid4()

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
        tags if tags else [],
        content_sin_vueltas,
        content_lo_central,
        content_en_profundidad,
        json.dumps(media) if media else json.dumps([])
    )

    # Update scraping item
    await conn.execute(
        """
        UPDATE scraping_items
        SET publication_id = $1,
            published_at = NOW(),
            status = 'published',
            status_message = 'Publicado por curador',
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


async def publish_items(pool, items: List[Dict], log_func=None) -> int:
    """Publish the selected items by creating publications"""
    if not items:
        return 0

    published_count = 0

    async with pool.acquire() as conn:
        for item in items:
            try:
                result = await create_publication(conn, item)
                if "error" not in result:
                    published_count += 1
                    if log_func:
                        log_func(f"Published: {item.get('ai_title', item.get('title', ''))[:50]}...", "INFO")
                else:
                    if log_func:
                        log_func(f"Failed to publish item {item['id']}: {result['error']}", "WARN")
            except Exception as e:
                if log_func:
                    log_func(f"Error publishing item {item['id']}: {str(e)[:100]}", "ERROR")

    return published_count


async def curate_and_publish(
    pool,
    target_count: int = 12,
    max_per_category: int = 3,
    max_per_source: int = 3,
    dry_run: bool = False,
    log_func=None
) -> Dict[str, Any]:
    """
    Main curation function:
    1. Get all ready_to_publish items
    2. Apply selection algorithm
    3. Publish selected items (unless dry_run)

    Returns statistics about the curation.
    """
    def log(msg, level="INFO"):
        if log_func:
            log_func(msg, level)
        else:
            print(f"[{level}] {msg}")

    log(f"Starting news curation (target: {target_count} items)")

    # Get all ready items
    all_items = await get_ready_to_publish_items(pool)
    log(f"Found {len(all_items)} items ready to publish")

    if not all_items:
        log("No items to curate", "WARN")
        return {
            "success": True,
            "total_available": 0,
            "selected_count": 0,
            "published_count": 0,
            "dry_run": dry_run
        }

    # Apply selection algorithm
    selected = select_curated_items(
        all_items,
        target_count=target_count,
        max_per_category=max_per_category,
        max_per_source=max_per_source
    )

    log(f"Selected {len(selected)} items for publication")

    # Log selection details
    by_category = defaultdict(int)
    by_source = defaultdict(int)
    for item in selected:
        by_category[item.get('category') or 'general'] += 1
        by_source[item.get('source_name', 'Unknown')] += 1

    log(f"Categories: {dict(by_category)}")
    log(f"Sources: {dict(by_source)}")

    if dry_run:
        log("DRY RUN - No items published")
        return {
            "success": True,
            "total_available": len(all_items),
            "selected_count": len(selected),
            "published_count": 0,
            "dry_run": True,
            "selected_items": [
                {
                    "id": str(item['id']),
                    "title": item['title'],
                    "category": item.get('category'),
                    "source": item.get('source_name')
                }
                for item in selected
            ],
            "by_category": dict(by_category),
            "by_source": dict(by_source)
        }

    # Publish selected items (pass full items, not just IDs)
    published_count = await publish_items(pool, selected, log_func)

    log(f"Curation complete: {published_count} items published")

    return {
        "success": True,
        "total_available": len(all_items),
        "selected_count": len(selected),
        "published_count": published_count,
        "dry_run": False,
        "by_category": dict(by_category),
        "by_source": dict(by_source)
    }


# For standalone execution
async def main():
    """Standalone execution for testing"""
    import asyncpg

    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ladatajusta")

    pool = await asyncpg.create_pool(DATABASE_URL)

    try:
        # Do a dry run first to see what would be selected
        result = await curate_and_publish(
            pool,
            target_count=12,
            max_per_category=3,
            max_per_source=3,
            dry_run=True
        )

        print("\n=== Dry Run Results ===")
        print(f"Total available: {result['total_available']}")
        print(f"Selected: {result['selected_count']}")
        print(f"By category: {result.get('by_category', {})}")
        print(f"By source: {result.get('by_source', {})}")

        if result.get('selected_items'):
            print("\nSelected items:")
            for item in result['selected_items']:
                print(f"  - [{item['category']}] {item['title'][:60]}... ({item['source']})")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
