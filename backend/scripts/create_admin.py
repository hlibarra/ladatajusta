"""
Script para crear el usuario admin inicial.
Ejecutar: python -m scripts.create_admin
"""
import asyncio
import sys
from pathlib import Path

# Fix for Windows event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.models import User
from app.db.session import AsyncSessionLocal, engine
from app.db.init_db import init_db


async def create_admin():
    # Initialize database tables first
    await init_db()

    async with AsyncSessionLocal() as db:
        # Check if admin exists
        existing = await db.scalar(select(User).where(User.email == "admin@local.com"))

        if existing:
            print("Usuario admin ya existe!")
            print(f"  Email: {existing.email}")
            print(f"  Admin: {existing.is_admin}")
            return

        # Create admin user
        admin = User(
            email="admin@local.com",
            hashed_password=get_password_hash("admin123"),
            is_active=True,
            is_admin=True,
        )

        db.add(admin)
        await db.commit()

        print("Usuario admin creado exitosamente!")
        print("  Email: admin@local.com")
        print("  Password: admin123")
        print("\nAccede al panel en: http://localhost:4321/admin")


if __name__ == "__main__":
    asyncio.run(create_admin())
