"""
API routes for site configuration.
Provides public read access to display settings and admin write access.
"""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentAdmin
from app.db.models import SiteConfig
from app.db.session import get_db

router = APIRouter()


@router.get("/display")
async def get_display_config(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get display configuration for the frontend.

    **Public endpoint** - No authentication required.

    Returns all display settings that affect how content is shown.
    """
    query = select(SiteConfig).where(SiteConfig.category == "display")
    result = await db.execute(query)
    configs = result.scalars().all()

    # Build response with just key-value pairs
    display_config = {}
    for config in configs:
        # Extract key name (remove 'display.' prefix)
        key_name = config.key.replace("display.", "")
        display_config[key_name] = config.value

    return display_config


@router.get("/features")
async def get_features_config(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get feature flags configuration.

    **Public endpoint** - No authentication required.

    Returns all feature flags that enable/disable functionality.
    """
    query = select(SiteConfig).where(SiteConfig.category == "features")
    result = await db.execute(query)
    configs = result.scalars().all()

    features_config = {}
    for config in configs:
        key_name = config.key.replace("features.", "")
        features_config[key_name] = config.value

    return features_config


@router.get("/all")
async def get_all_config(
    current_user: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Get all configuration entries.

    **Requires:** Admin authentication

    Returns full configuration details including descriptions.
    """
    query = select(SiteConfig).order_by(SiteConfig.category, SiteConfig.key)
    result = await db.execute(query)
    configs = result.scalars().all()

    return [
        {
            "key": config.key,
            "value": config.value,
            "description": config.description,
            "category": config.category,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        }
        for config in configs
    ]


@router.patch("/{config_key}")
async def update_config(
    config_key: str,
    value: Any,
    current_user: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Update a configuration value.

    **Requires:** Admin authentication

    Args:
        config_key: The configuration key (e.g., 'display.show_images')
        value: The new value (JSON-compatible)
    """
    # Get existing config
    query = select(SiteConfig).where(SiteConfig.key == config_key)
    result = await db.execute(query)
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail=f"Configuration '{config_key}' not found")

    # Update value
    config.value = value
    config.updated_at = datetime.utcnow()
    config.updated_by = current_user.id

    await db.commit()
    await db.refresh(config)

    return {
        "success": True,
        "key": config.key,
        "value": config.value,
        "updated_at": config.updated_at.isoformat(),
    }


@router.post("/bulk-update")
async def bulk_update_config(
    updates: dict[str, Any],
    current_user: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Update multiple configuration values at once.

    **Requires:** Admin authentication

    Args:
        updates: Dictionary of key-value pairs to update
    """
    updated_keys = []

    for key, value in updates.items():
        query = select(SiteConfig).where(SiteConfig.key == key)
        result = await db.execute(query)
        config = result.scalar_one_or_none()

        if config:
            config.value = value
            config.updated_at = datetime.utcnow()
            config.updated_by = current_user.id
            updated_keys.append(key)

    await db.commit()

    return {
        "success": True,
        "updated_keys": updated_keys,
        "count": len(updated_keys),
    }
