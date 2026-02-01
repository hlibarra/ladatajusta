from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentAdmin
from app.core.security import get_password_hash
from app.db.models import User
from app.db.session import get_db

router = APIRouter()


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    is_admin: bool = False


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    is_active: bool | None = None
    is_admin: bool | None = None


class UsersListResponse(BaseModel):
    users: list[UserOut]
    total: int


@router.get("", response_model=UsersListResponse)
async def list_users(
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
) -> UsersListResponse:
    """Lista todos los usuarios (solo admin)"""
    total = await db.scalar(select(func.count(User.id)))
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    )
    users = result.scalars().all()

    return UsersListResponse(
        users=[
            UserOut(
                id=u.id,
                email=u.email,
                is_active=u.is_active,
                is_admin=u.is_admin,
                created_at=u.created_at,
            )
            for u in users
        ],
        total=total or 0,
    )


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    """Obtiene un usuario por ID (solo admin)"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    return UserOut(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    """Crea un nuevo usuario (solo admin)"""
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya esta registrado",
        )

    user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        is_active=True,
        is_admin=payload.is_admin,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserOut(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    """Actualiza un usuario (solo admin)"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    # Prevent admin from deactivating themselves or removing their own admin status
    if user.id == admin.id:
        if payload.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes desactivarte a ti mismo",
            )
        if payload.is_admin is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes quitarte los permisos de admin a ti mismo",
            )

    if payload.email is not None:
        # Check if email is already taken by another user
        existing = await db.scalar(
            select(User).where(User.email == payload.email, User.id != user_id)
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya esta en uso",
            )
        user.email = payload.email

    if payload.password is not None:
        user.hashed_password = get_password_hash(payload.password)

    if payload.is_active is not None:
        user.is_active = payload.is_active

    if payload.is_admin is not None:
        user.is_admin = payload.is_admin

    await db.commit()
    await db.refresh(user)

    return UserOut(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_user(
    user_id: uuid.UUID,
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db),
):
    """Elimina un usuario (solo admin)"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    # Prevent admin from deleting themselves
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminarte a ti mismo",
        )

    await db.delete(user)
    await db.commit()
