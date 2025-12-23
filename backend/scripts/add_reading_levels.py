"""
Script para agregar columnas de niveles de lectura a publications y users.
Ejecutar: python -m scripts.add_reading_levels
"""
import asyncio
import sys
from pathlib import Path

# Fix for Windows event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import engine
from sqlalchemy import text


async def add_reading_levels():
    async with engine.begin() as conn:
        print("Agregando columnas de niveles de lectura...\n")

        # Add reading level columns to publications
        try:
            await conn.execute(
                text("""
                    ALTER TABLE publications
                    ADD COLUMN IF NOT EXISTS content_sin_vueltas TEXT,
                    ADD COLUMN IF NOT EXISTS content_lo_central TEXT,
                    ADD COLUMN IF NOT EXISTS content_en_profundidad TEXT
                """)
            )
            print("✓ Columnas de contenido por nivel agregadas a publications")
        except Exception as e:
            print(f"✗ Error al agregar columnas a publications: {e}")

        # Add preferred reading level to users
        try:
            await conn.execute(
                text("""
                    ALTER TABLE users
                    ADD COLUMN IF NOT EXISTS preferred_reading_level VARCHAR(32) DEFAULT 'lo_central'
                """)
            )
            print("✓ Columna preferred_reading_level agregada a users")
        except Exception as e:
            print(f"✗ Error al agregar columna a users: {e}")

        # Update existing users to have default reading level
        try:
            await conn.execute(
                text("""
                    UPDATE users
                    SET preferred_reading_level = 'lo_central'
                    WHERE preferred_reading_level IS NULL
                """)
            )
            print("✓ Usuarios existentes actualizados con nivel por defecto")
        except Exception as e:
            print(f"✗ Error al actualizar usuarios: {e}")

        print("\n¡Migración completada exitosamente!")


if __name__ == "__main__":
    asyncio.run(add_reading_levels())
