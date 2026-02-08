from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional
from app.api.schemas import ReadingLevelPreference, SourcesPreference, UserPreferences
from app.db.session import get_db
from app.db.models import User

router = APIRouter()


@router.get("/preferences", response_model=UserPreferences)
async def get_user_preferences(
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtener las preferencias del usuario autenticado.
    Si el usuario no está autenticado, devuelve el valor por defecto.
    """
    if not current_user:
        return UserPreferences(preferred_reading_level="lo_central", preferred_sources=None)

    return UserPreferences(
        preferred_reading_level=current_user.preferred_reading_level,
        preferred_sources=current_user.preferred_sources
    )


@router.put("/preferences/reading-level", response_model=UserPreferences)
async def update_reading_level_preference(
    preference: ReadingLevelPreference,
    current_user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Actualizar la preferencia de nivel de lectura del usuario.
    Requiere autenticación.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Debes iniciar sesión para guardar preferencias")

    current_user.preferred_reading_level = preference.preferred_reading_level
    await db.commit()
    await db.refresh(current_user)

    return UserPreferences(
        preferred_reading_level=current_user.preferred_reading_level,
        preferred_sources=current_user.preferred_sources
    )


@router.put("/preferences/sources", response_model=UserPreferences)
async def update_sources_preference(
    preference: SourcesPreference,
    current_user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Actualizar la preferencia de fuentes de scraping del usuario.
    Requiere autenticación.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Debes iniciar sesión para guardar preferencias")

    current_user.preferred_sources = preference.preferred_sources
    await db.commit()
    await db.refresh(current_user)

    return UserPreferences(
        preferred_reading_level=current_user.preferred_reading_level,
        preferred_sources=current_user.preferred_sources
    )
