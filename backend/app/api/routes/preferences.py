from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_user_optional
from app.api.schemas import ReadingLevelPreference, UserPreferences
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
        return UserPreferences(preferred_reading_level="lo_central")

    return UserPreferences(preferred_reading_level=current_user.preferred_reading_level)


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

    return UserPreferences(preferred_reading_level=current_user.preferred_reading_level)
