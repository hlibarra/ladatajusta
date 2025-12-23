"""
Script para verificar si existe el usuario admin.
Ejecutar: python -m scripts.check_admin
"""
import asyncio
import sys
from pathlib import Path

# Fix for Windows event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.models import User
from app.db.session import AsyncSessionLocal
from sqlalchemy import select


async def check_admin():
    async with AsyncSessionLocal() as db:
        # Get admin user
        result = await db.execute(
            select(User).where(User.email == "admin@local.com")
        )
        admin = result.scalar_one_or_none()

        if admin:
            print(f"Usuario encontrado:")
            print(f"  Email: {admin.email}")
            print(f"  Is Admin: {admin.is_admin}")
            print(f"  Is Active: {admin.is_active}")
            print(f"  Created: {admin.created_at}")
        else:
            print("Usuario admin@local.com NO encontrado en la base de datos.")
            print("\nEjecuta: python -m scripts.create_admin")


if __name__ == "__main__":
    asyncio.run(check_admin())
