"""
Script para resetear la contraseña del usuario admin.
Ejecutar: python -m scripts.reset_admin_password
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
from app.core.security import get_password_hash
from sqlalchemy import select


async def reset_admin_password():
    async with AsyncSessionLocal() as db:
        # Get admin user
        result = await db.execute(
            select(User).where(User.email == "admin@local.com")
        )
        admin = result.scalar_one_or_none()

        if not admin:
            print("Usuario admin@local.com NO encontrado.")
            print("Ejecuta: python -m scripts.create_admin")
            return

        # Reset password
        new_password = "admin123"
        admin.hashed_password = get_password_hash(new_password)

        await db.commit()

        print("Contraseña del admin reseteada exitosamente!")
        print(f"  Email: {admin.email}")
        print(f"  Nueva contraseña: {new_password}")
        print("\nPuedes iniciar sesión en: http://localhost:4321/admin/login")


if __name__ == "__main__":
    asyncio.run(reset_admin_password())
